"""Bounded, local-only PipeWire, whisper.cpp, and Piper provider adapters."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import os
from pathlib import Path
import select
import shutil
import signal
import stat
import subprocess
import tempfile
from threading import Event, Thread
import time
from typing import Callable, Sequence
import wave

from .providers import (
    AudioCapture,
    SpeechPlaybackCancelled,
    SpeechPlaybackError,
    SpeechPlaybackTimeout,
    SpeechSynthesisCancelled,
    SpeechSynthesisError,
    SpeechSynthesisTimeout,
    SynthesizedSpeech,
    Transcript,
)


MIN_CAPTURE_SECONDS = 1
MAX_CAPTURE_SECONDS = 30
MIN_STT_THREADS = 1
MAX_STT_THREADS = 3
MIN_STT_TIMEOUT_SECONDS = 1
MAX_STT_TIMEOUT_SECONDS = 60
MIN_TTS_SYNTHESIS_TIMEOUT_SECONDS = 1
MAX_TTS_SYNTHESIS_TIMEOUT_SECONDS = 30
MIN_TTS_PLAYBACK_TIMEOUT_SECONDS = 1
MAX_TTS_PLAYBACK_TIMEOUT_SECONDS = 60
SUPPORTED_STT_LANGUAGES = {'auto', 'en', 'de'}
MAX_CHILD_OUTPUT_BYTES = 64 * 1024
MAX_WHISPER_JSON_BYTES = 1 * 1024 * 1024
MAX_CAPTURE_WAV_BYTES = MAX_CAPTURE_SECONDS * 16000 * 2 + 4096
MAX_PIPER_WAV_BYTES = 8 * 1024 * 1024
CHILD_ENVIRONMENT_KEYS = (
    'PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ', 'XDG_RUNTIME_DIR',
    'DBUS_SESSION_BUS_ADDRESS', 'PIPEWIRE_RUNTIME_DIR', 'PIPEWIRE_REMOTE',
    'PIPEWIRE_LATENCY', 'PIPEWIRE_CONFIG_DIR', 'PIPEWIRE_CONFIG_PREFIX',
    'PIPEWIRE_MODULE_DIR', 'SPA_PLUGIN_DIR', 'LD_LIBRARY_PATH',
)


class LocalProviderError(RuntimeError):
    """Base error for a local executable, asset, or device failure."""


class CaptureError(LocalProviderError):
    """PipeWire microphone capture failed without producing usable audio."""


class SttError(LocalProviderError):
    """whisper.cpp could not return a deterministic transcript."""


def _bounded_int(value: object, *, name: str, minimum: int, maximum: int) -> int:
    """Validate one documented integral runtime bound."""
    if isinstance(value, bool):
        raise ValueError(f'{name} must be an integer from {minimum} to {maximum}')
    try:
        converted = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{name} must be an integer from {minimum} to {maximum}') from error
    if converted != value or not minimum <= converted <= maximum:
        raise ValueError(f'{name} must be an integer from {minimum} to {maximum}')
    return converted


def validate_capture_seconds(value: object) -> int:
    """Validate the profile's 1--30 second capture limit."""
    return _bounded_int(value, name='maximum_capture_seconds', minimum=MIN_CAPTURE_SECONDS,
                        maximum=MAX_CAPTURE_SECONDS)


def validate_stt_threads(value: object) -> int:
    """Validate the profile's 1--3 whisper.cpp thread limit."""
    return _bounded_int(value, name='stt_threads', minimum=MIN_STT_THREADS,
                        maximum=MAX_STT_THREADS)


def validate_stt_timeout_seconds(value: object) -> int:
    """Validate the profile's 1--60 second transcription timeout."""
    return _bounded_int(value, name='stt_timeout_seconds', minimum=MIN_STT_TIMEOUT_SECONDS,
                        maximum=MAX_STT_TIMEOUT_SECONDS)


def validate_tts_synthesis_timeout_seconds(value: object) -> int:
    """Validate the profile's 1--30 second Piper synthesis timeout."""
    return _bounded_int(value, name='tts_synthesis_timeout_seconds',
                        minimum=MIN_TTS_SYNTHESIS_TIMEOUT_SECONDS,
                        maximum=MAX_TTS_SYNTHESIS_TIMEOUT_SECONDS)


def validate_tts_playback_timeout_seconds(value: object) -> int:
    """Validate the profile's 1--60 second PipeWire playback timeout."""
    return _bounded_int(value, name='tts_playback_timeout_seconds',
                        minimum=MIN_TTS_PLAYBACK_TIMEOUT_SECONDS,
                        maximum=MAX_TTS_PLAYBACK_TIMEOUT_SECONDS)


def validate_stt_language(value: str) -> str:
    """Accept only automatic recognition or the two supported language hints."""
    language = str(value).lower()
    if language not in SUPPORTED_STT_LANGUAGES:
        raise ValueError('stt_language must be one of auto, en, de')
    return language


def _executable(value: str | Path, label: str) -> str:
    """Resolve an executable to an absolute executable path before invocation."""
    requested = str(value)
    resolved = Path(requested) if Path(requested).is_absolute() else shutil.which(requested)
    if resolved is None:
        raise LocalProviderError(f'{label} executable is unavailable: {requested}')
    path = Path(resolved).resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise LocalProviderError(f'{label} executable is unavailable: {path}')
    return str(path)


def _asset(value: str | Path, label: str) -> Path:
    """Require an explicit existing local model/configuration file."""
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise LocalProviderError(f'{label} file is unavailable: {path}')
    return path


def _private_directory(base: Path | None, prefix: str) -> Path:
    """Create a provider-owned, mode-0700 directory for one local process."""
    parent = base or Path('/tmp')
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir=str(parent)))
    directory.chmod(0o700)
    return directory


def _remove_owned_directory(directory: Path | None) -> None:
    """Remove one known provider-owned private directory and all its outputs."""
    if directory is not None:
        shutil.rmtree(directory, ignore_errors=True)


def _open_bounded_regular_file(path: Path, maximum_bytes: int, label: str):
    """Open a non-symlink regular file after enforcing a strict byte bound."""
    flags = os.O_RDONLY | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ValueError(f'{label} is unavailable or unsafe: {error}') from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f'{label} must be a regular file')
        if metadata.st_size > maximum_bytes:
            raise ValueError(f'{label} exceeds {maximum_bytes} bytes')
        return os.fdopen(descriptor, 'rb')
    except Exception:
        os.close(descriptor)
        raise


def _read_bounded_json(path: Path) -> object:
    """Read a bounded private whisper JSON file without following symlinks."""
    try:
        with _open_bounded_regular_file(path, MAX_WHISPER_JSON_BYTES, 'whisper JSON') as source:
            payload = source.read(MAX_WHISPER_JSON_BYTES + 1)
    except (OSError, ValueError) as error:
        raise SttError(f'whisper.cpp produced unsafe JSON: {error}') from error
    if len(payload) > MAX_WHISPER_JSON_BYTES:
        raise SttError('whisper.cpp JSON exceeds maximum size')
    try:
        return json.loads(payload.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SttError(f'whisper.cpp produced invalid JSON: {error}') from error


def _child_environment() -> dict[str, str]:
    """Return only local runtime variables needed by PipeWire and native binaries."""
    return {
        key: os.environ[key]
        for key in CHILD_ENVIRONMENT_KEYS
        if key in os.environ
    }


@dataclass
class _ChildProcess:
    """An owned child with concurrently drained, bounded diagnostic output."""

    process: subprocess.Popen[bytes]
    stdout: bytearray
    stderr: bytearray
    stdout_truncated: list[bool]
    stderr_truncated: list[bool]
    drains: tuple[Thread, Thread]
    process_group_id: int
    session_id: int

    def poll(self) -> int | None:
        """Return the underlying child status without exposing its process API."""
        return self.process.poll()


def _drain(stream: object, output: bytearray, truncated: list[bool]) -> None:
    """Drain a child stream continuously while retaining a fixed diagnostic prefix."""
    while True:
        chunk = stream.read(4096)
        if not chunk:
            return
        available = MAX_CHILD_OUTPUT_BYTES - len(output)
        if available > 0:
            output.extend(chunk[:available])
        if len(chunk) > available:
            truncated[0] = True


def _owned_group_alive(child: _ChildProcess) -> bool:
    """Confirm an owned Linux process group remains before signalling its PGID."""
    if child.process.poll() is None:
        return True
    proc_root = Path('/proc')
    if not proc_root.is_dir():
        return False
    for entry in proc_root.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            remainder = (entry / 'stat').read_text(encoding='utf-8').rsplit(')', 1)[1].split()
            process_group_id, session_id = int(remainder[2]), int(remainder[3])
        except (IndexError, OSError, ValueError):
            continue
        if (process_group_id, session_id) == (child.process_group_id, child.session_id):
            return True
    return False


def _wait_for_owned_group(child: _ChildProcess, timeout_seconds: float) -> bool:
    """Wait only for the recorded provider group, never a reused arbitrary PGID."""
    deadline = time.monotonic() + timeout_seconds
    while _owned_group_alive(child):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)
    return True


def _terminate(child: _ChildProcess, *, first_signal: int = signal.SIGTERM) -> None:
    """Stop an owned group with the requested graceful signal, TERM, then KILL."""
    if not _owned_group_alive(child):
        return
    try:
        os.killpg(child.process_group_id, first_signal)
    except ProcessLookupError:
        return
    if not _wait_for_owned_group(child, 0.25):
        if first_signal != signal.SIGTERM and _owned_group_alive(child):
            try:
                os.killpg(child.process_group_id, signal.SIGTERM)
            except ProcessLookupError:
                return
        if not _wait_for_owned_group(child, 0.25) and _owned_group_alive(child):
            try:
                os.killpg(child.process_group_id, signal.SIGKILL)
            except ProcessLookupError:
                return
            _wait_for_owned_group(child, 0.25)
    if child.process.poll() is None:
        try:
            child.process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            pass


def _start(argv: list[str], *, stdin: bool = False) -> _ChildProcess:
    """Start an argv-only child while draining bounded stdout/stderr concurrently."""
    process = subprocess.Popen(
        argv,
        env=_child_environment(),
        stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stdout, stderr = bytearray(), bytearray()
    stdout_truncated, stderr_truncated = [False], [False]
    assert process.stdout is not None and process.stderr is not None
    drains = (
        Thread(target=_drain, args=(process.stdout, stdout, stdout_truncated), daemon=True),
        Thread(target=_drain, args=(process.stderr, stderr, stderr_truncated), daemon=True),
    )
    for drain in drains:
        drain.start()
    return _ChildProcess(
        process, stdout, stderr, stdout_truncated, stderr_truncated, drains,
        process.pid, process.pid)


def _finish(child: _ChildProcess) -> tuple[str, str]:
    """Join stream drains and return bounded, explicitly truncated diagnostics."""
    for drain in child.drains:
        drain.join(0.25)
    return (
        _output_text(child.stdout, child.stdout_truncated[0]),
        _output_text(child.stderr, child.stderr_truncated[0]),
    )


def _output_text(output: bytearray, truncated: bool) -> str:
    """Decode a retained output prefix without hiding truncation from diagnostics."""
    suffix = ' [output truncated]' if truncated else ''
    return output.decode(errors='replace') + suffix


def _deliver_piper_stdin(
        child: _ChildProcess,
        text: str,
        *,
        cancel_event: Event,
        deadline_monotonic: float) -> None:
    """Write Piper text without a blocking pipe write or detached worker."""
    stdin = child.process.stdin
    if stdin is None:
        raise SpeechSynthesisError('Piper stdin is unavailable')
    payload = text.encode()
    offset = 0
    try:
        descriptor = stdin.fileno()
        os.set_blocking(descriptor, False)
        while offset < len(payload):
            if cancel_event.is_set():
                raise SpeechSynthesisCancelled('Piper synthesis cancelled')
            remaining = deadline_monotonic - time.monotonic()
            if remaining <= 0.0:
                raise SpeechSynthesisTimeout('Piper synthesis timed out')
            try:
                _, writable, _ = select.select([], [descriptor], [], min(0.05, remaining))
            except OSError as error:
                raise SpeechSynthesisError(f'Piper stdin delivery failed: {error}') from error
            if not writable:
                continue
            try:
                written = os.write(descriptor, payload[offset:offset + 65_536])
            except (BlockingIOError, InterruptedError):
                continue
            except BrokenPipeError as error:
                raise SpeechSynthesisError('Piper closed stdin before synthesis') from error
            if written <= 0:
                raise SpeechSynthesisError('Piper accepted no synthesis input')
            offset += written
        if cancel_event.is_set():
            raise SpeechSynthesisCancelled('Piper synthesis cancelled')
        if time.monotonic() >= deadline_monotonic:
            raise SpeechSynthesisTimeout('Piper synthesis timed out')
    finally:
        # No data is buffered in this Python stream: writes above use os.write.
        # Closing delivers EOF without leaving a background writer alive.
        try:
            stdin.close()
        except BrokenPipeError:
            pass


def _pcm_wav_properties(
        path: Path, maximum_bytes: int, label: str) -> tuple[int, int, int, int, str]:
    """Return frames/rate/channels/sample width for a readable non-empty PCM WAV."""
    try:
        with _open_bounded_regular_file(path, maximum_bytes, label) as source:
            with wave.open(source, 'rb') as reader:
                properties = (
                    reader.getnframes(),
                    reader.getframerate(),
                    reader.getnchannels(),
                    reader.getsampwidth(),
                    reader.getcomptype(),
                )
    except (wave.Error, OSError, ValueError) as error:
        raise ValueError(f'not a readable WAV: {error}') from error
    frames, rate, channels, sample_width, compression = properties
    if compression != 'NONE' or not all(value > 0 for value in properties[:4]):
        raise ValueError('must be a non-empty PCM WAV with positive audio properties')
    return properties


def _validate_capture_wav(path: Path) -> float:
    """Require PipeWire microphone capture to be 16-bit PCM, 16 kHz, mono."""
    try:
        frames, rate, channels, sample_width, _compression = _pcm_wav_properties(
            path, MAX_CAPTURE_WAV_BYTES, 'PipeWire capture WAV')
    except ValueError as error:
        raise CaptureError(f'PipeWire capture {error}') from error
    if (sample_width, rate, channels) != (2, 16000, 1):
        raise CaptureError('PipeWire capture must be 16-bit PCM WAV at 16 kHz mono')
    return frames / rate


def _validate_piper_wav(path: Path) -> float:
    """Accept Piper's native PCM WAV rate/channels and report its true duration."""
    try:
        frames, rate, _channels, _sample_width, _compression = _pcm_wav_properties(
            path, MAX_PIPER_WAV_BYTES, 'Piper output WAV')
    except ValueError as error:
        raise SpeechSynthesisError(f'Piper output {error}') from error
    return frames / rate


class PipeWirePushToTalkAudioInput:
    """Captures one temporary 16 kHz mono WAV when a terminal PTT cycle ends."""

    def __init__(
            self,
            *,
            record_binary: str | Path = 'pw-record',
            device: str | None = None,
            maximum_capture_seconds: int = 15,
            locale: str = 'en-US',
            temp_directory: str | Path | None = None) -> None:
        self._record_binary = _executable(record_binary, 'PipeWire capture')
        self._device = device or None
        self._maximum_capture_seconds = validate_capture_seconds(maximum_capture_seconds)
        self._locale = locale
        self._temp_directory = Path(temp_directory) if temp_directory else None
        self._captures: deque[AudioCapture] = deque()

    def next_capture(self) -> AudioCapture | None:
        """Return a completed terminal capture to the regular voice node."""
        return self._captures.popleft() if self._captures else None

    def close(self) -> None:
        """Discard any completed recording that was not handed to STT yet."""
        while self._captures:
            capture = self._captures.popleft()
            if capture.audio_path is not None:
                capture.audio_path.unlink(missing_ok=True)
            _remove_owned_directory(capture.cleanup_directory)

    def capture_once(self, release_event: Event) -> AudioCapture:
        """Record until release or the configured maximum, then queue one WAV."""
        directory = _private_directory(self._temp_directory, 'buddy-capture-')
        audio_path = directory / 'capture.wav'
        # pw-record/pw-play are commonly symlinks to pw-cat. Always request the
        # operation explicitly because executable resolution intentionally
        # yields the pw-cat target rather than the wrapper basename.
        argv = [
            self._record_binary, '--record', '--format', 's16', '--rate', '16000',
            '--channels', '1',
        ]
        if self._device:
            argv.extend(['--target', self._device])
        argv.append(str(audio_path))
        try:
            process = _start(argv)
        except OSError as error:
            _remove_owned_directory(directory)
            raise CaptureError(f'PipeWire capture could not start: {error}') from error
        deadline = time.monotonic() + self._maximum_capture_seconds
        try:
            while process.poll() is None and not release_event.is_set() and time.monotonic() < deadline:
                release_event.wait(min(0.05, max(0.0, deadline - time.monotonic())))
            if process.poll() is None:
                # pw-record finalizes WAV headers on SIGINT; only escalate when
                # it ignores the graceful stop request.
                _terminate(process, first_signal=signal.SIGINT)
            _, stderr = _finish(process)
            if not audio_path.exists():
                raise CaptureError(f'PipeWire capture produced no WAV: {stderr.strip()}')
            _validate_capture_wav(audio_path)
        except Exception:
            if process.poll() is None:
                _terminate(process)
            _remove_owned_directory(directory)
            raise
        capture = AudioCapture(b'', 0, self._locale, audio_path, directory)
        self._captures.append(capture)
        return capture


def _transcript_from_json(payload: object, locale: str) -> str:
    """Read only documented, deterministic text fields from whisper JSON output."""
    if isinstance(payload, dict):
        text = payload.get('text')
        if isinstance(text, str):
            return text.strip()
        segments = payload.get('transcription', payload.get('segments'))
        if isinstance(segments, list):
            return ''.join(
                item.get('text', '') for item in segments
                if isinstance(item, dict) and isinstance(item.get('text', ''), str)).strip()
    raise SttError(f'whisper.cpp returned invalid JSON transcript for {locale}')


def _is_no_speech_sentinel(text: str) -> bool:
    """Recognize whisper.cpp's exact blank-audio sentinel without broad filtering."""
    return text.strip().casefold() == '[blank_audio]'


def _auto_locale_from_json(payload: object, fallback_locale: str) -> str:
    """Map whisper's detected English/German language or use an explicit fallback."""
    if not isinstance(payload, dict):
        return fallback_locale
    result = payload.get('result')
    candidates = [payload.get('language')]
    if isinstance(result, dict):
        candidates.append(result.get('language'))
    detected = next((item for item in candidates if item is not None), None)
    if detected is None:
        return fallback_locale
    if isinstance(detected, dict):
        detected = detected.get('code')
    if not isinstance(detected, str):
        raise SttError('whisper.cpp returned an invalid detected language')
    language = detected.lower()
    if language == 'en':
        return 'en-US'
    if language == 'de':
        return 'de-DE'
    raise SttError(f'whisper.cpp detected unsupported language: {detected}')


class WhisperCppSpeechToTextProvider:
    """One-shot multilingual whisper.cpp adapter that deletes every source WAV."""

    def __init__(
            self,
            *,
            binary: str | Path,
            model: str | Path,
            threads: int = 2,
            timeout_seconds: int = 30,
            language: str = 'auto') -> None:
        self._binary = _executable(binary, 'whisper.cpp')
        self._model = _asset(model, 'whisper.cpp model')
        self._threads = validate_stt_threads(threads)
        self._timeout_seconds = validate_stt_timeout_seconds(timeout_seconds)
        self._language = validate_stt_language(language)

    def transcribe(self, capture: AudioCapture) -> Sequence[Transcript]:
        """Run whisper-cli once, parse its JSON, and remove all transient audio."""
        if capture.audio_path is None:
            raise SttError('whisper.cpp requires a local WAV capture path')
        audio_path = capture.audio_path
        output_directory = _private_directory(None, 'buddy-whisper-')
        output_base = output_directory / 'output'
        output_json = output_base.with_suffix('.json')
        argv = [self._binary, '-m', str(self._model), '-f', str(audio_path), '-t', str(self._threads),
                '-l', self._language, '-oj', '-of', str(output_base)]
        process: _ChildProcess | None = None
        try:
            process = _start(argv)
            deadline = time.monotonic() + self._timeout_seconds
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    _terminate(process)
                    raise SttError('whisper.cpp transcription timed out')
                time.sleep(0.01)
            _, stderr = _finish(process)
            if process.process.returncode != 0:
                raise SttError(
                    f'whisper.cpp exited with {process.process.returncode}: {stderr.strip()}')
            payload = _read_bounded_json(output_json)
            text = _transcript_from_json(payload, capture.locale)
            if not text:
                raise SttError('whisper.cpp produced an empty final transcript')
            if _is_no_speech_sentinel(text):
                raise SttError('whisper.cpp produced no usable utterance')
            locale = (
                'de-DE' if self._language == 'de'
                else 'en-US' if self._language == 'en'
                else _auto_locale_from_json(payload, capture.locale)
            )
            return [Transcript(text, 1.0, True, locale)]
        finally:
            if process is not None and process.poll() is None:
                _terminate(process)
            if process is not None:
                _finish(process)
            audio_path.unlink(missing_ok=True)
            _remove_owned_directory(capture.cleanup_directory)
            _remove_owned_directory(output_directory)


@dataclass(frozen=True)
class PiperVoice:
    """An explicit Piper model/config pair for one supported locale."""

    name: str
    locale: str
    model: Path
    config: Path


def _default_locale_for_text(text: str) -> str:
    """Use German for an obvious German final utterance; English otherwise."""
    lower = text.lower()
    german_markers = ('ä', 'ö', 'ü', 'ß', ' bitte ', ' danke ', ' der ', ' die ', ' das ', ' ist ')
    return 'de' if any(marker in lower for marker in german_markers) else 'en'


class PiperTextToSpeechProvider:
    """Piper synthesis plus PipeWire playback with independently bounded phases."""

    def __init__(
            self,
            *,
            piper_binary: str | Path,
            playback_binary: str | Path = 'pw-play',
            english_voice: PiperVoice,
            german_voice: PiperVoice,
            sink: str | None = None,
            synthesis_timeout_seconds: int = 15,
            playback_timeout_seconds: int = 30,
            temp_directory: str | Path | None = None) -> None:
        self._piper_binary = _executable(piper_binary, 'Piper')
        self._playback_binary = _executable(playback_binary, 'PipeWire playback')
        self._voices = {english_voice.name: english_voice, german_voice.name: german_voice}
        if (
                len(self._voices) != 2
                or not english_voice.name.startswith('en_')
                or not german_voice.name.startswith('de_')
                or english_voice.locale.split('-')[0] != 'en'
                or german_voice.locale.split('-')[0] != 'de'):
            raise ValueError('Piper requires one uniquely named en_* and one uniquely named de_* voice')
        for voice in self._voices.values():
            _asset(voice.model, f'Piper {voice.name} model')
            _asset(voice.config, f'Piper {voice.name} config')
        self._english_voice = english_voice.name
        self._german_voice = german_voice.name
        self._sink = sink or None
        self._synthesis_timeout_seconds = validate_tts_synthesis_timeout_seconds(synthesis_timeout_seconds)
        self._playback_timeout_seconds = validate_tts_playback_timeout_seconds(playback_timeout_seconds)
        self._temp_directory = Path(temp_directory) if temp_directory else None

    def _select_voice(self, text: str, requested: str) -> PiperVoice:
        if requested:
            if requested not in self._voices:
                raise SpeechSynthesisError(f'unknown configured voice: {requested}')
            return self._voices[requested]
        return self._voices[self._german_voice if _default_locale_for_text(text) == 'de' else self._english_voice]

    def synthesize(
            self, text: str, voice: str, *, cancel_event: Event,
            deadline_monotonic: float) -> SynthesizedSpeech:
        """Synthesize a temporary WAV, without starting playback."""
        selected = self._select_voice(text, voice)
        directory = _private_directory(self._temp_directory, 'buddy-piper-')
        wav_path = directory / 'output.wav'
        argv = [self._piper_binary, '--model', str(selected.model), '--config', str(selected.config),
                '--output_file', str(wav_path)]
        process: _ChildProcess | None = None
        deadline = min(deadline_monotonic, time.monotonic() + self._synthesis_timeout_seconds)
        try:
            process = _start(argv, stdin=True)
            _deliver_piper_stdin(
                process,
                text,
                cancel_event=cancel_event,
                deadline_monotonic=deadline,
            )
            while process.poll() is None:
                if cancel_event.is_set():
                    _terminate(process)
                    raise SpeechSynthesisCancelled('Piper synthesis cancelled')
                if time.monotonic() >= deadline:
                    _terminate(process)
                    raise SpeechSynthesisTimeout('Piper synthesis timed out')
                time.sleep(0.01)
            _, stderr = _finish(process)
            if process.process.returncode != 0:
                raise SpeechSynthesisError(
                    f'Piper exited with {process.process.returncode}: {stderr.strip()}')
            duration = _validate_piper_wav(wav_path)
            return SynthesizedSpeech(duration, wav_path, directory)
        except (SpeechSynthesisCancelled, SpeechSynthesisTimeout, SpeechSynthesisError):
            if process is not None and process.poll() is None:
                _terminate(process)
            _remove_owned_directory(directory)
            raise
        except Exception as error:
            if process is not None and process.poll() is None:
                _terminate(process)
            _remove_owned_directory(directory)
            raise SpeechSynthesisError(f'Piper synthesis failed: {error}') from error
        finally:
            if process is not None and process.poll() is None:
                _terminate(process)
            if process is not None:
                _finish(process)

    def play(self, speech: SynthesizedSpeech, *, cancel_event: Event, deadline_monotonic: float) -> None:
        """Play a synthesized WAV and terminate PipeWire promptly on cancellation."""
        if speech.audio_path is None or not speech.audio_path.is_file():
            raise SpeechPlaybackError('Piper playback WAV is unavailable')
        argv = [self._playback_binary, '--playback']
        if self._sink:
            argv.extend(['--target', self._sink])
        argv.append(str(speech.audio_path))
        try:
            process = _start(argv)
        except OSError as error:
            raise SpeechPlaybackError(f'PipeWire playback could not start: {error}') from error
        deadline = min(deadline_monotonic, time.monotonic() + self._playback_timeout_seconds)
        try:
            while process.poll() is None:
                if cancel_event.is_set():
                    _terminate(process)
                    raise SpeechPlaybackCancelled('PipeWire playback cancelled')
                if time.monotonic() >= deadline:
                    _terminate(process)
                    raise SpeechPlaybackTimeout('PipeWire playback timed out')
                time.sleep(0.01)
            _, stderr = _finish(process)
            if process.process.returncode != 0:
                raise SpeechPlaybackError(
                    f'PipeWire playback exited with {process.process.returncode}: {stderr.strip()}')
        finally:
            if process.poll() is None:
                _terminate(process)
            _finish(process)

    def cleanup(self, speech: SynthesizedSpeech) -> None:
        """Delete the provider-owned WAV after every terminal action outcome."""
        if speech.audio_path is not None:
            speech.audio_path.unlink(missing_ok=True)
        _remove_owned_directory(speech.cleanup_directory)


class OptionalWakeWordProvider:
    """Explicit optional boundary; no model means disabled, never a substitute phrase."""

    def __init__(self, detector: Callable[[bytes], bool] | None = None, *, model: str | Path | None = None) -> None:
        self._detector = detector
        self._model = _asset(model, 'wake-word') if model is not None else None

    @property
    def available(self) -> bool:
        """Return true only when an injected local detector and its model exist."""
        return self._detector is not None and self._model is not None

    def detected(self, samples: bytes) -> bool:
        """Fail closed when the optional local Buddy wake-word runtime is absent."""
        return bool(self._detector(samples)) if self.available and self._detector else False
