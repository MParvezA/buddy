"""Component tests for local providers using only temporary fake executables."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from threading import Event, Thread
import time

from buddy_voice.local_providers import (
    _finish,
    _is_no_speech_sentinel,
    _start,
    _terminate,
    LocalProviderError,
    MAX_SPEECH_INPUT_UTF8_BYTES,
    OptionalWakeWordProvider,
    PiperTextToSpeechProvider,
    PiperVoice,
    PipeWirePushToTalkAudioInput,
    SpeechPlaybackCancelled,
    SttError,
    validate_capture_seconds,
    validate_stt_language,
    validate_stt_threads,
    validate_stt_timeout_seconds,
    validate_tts_playback_timeout_seconds,
    validate_tts_synthesis_timeout_seconds,
    WhisperCppSpeechToTextProvider,
)
from buddy_voice.providers import (
    SpeechSynthesisCancelled,
    SpeechSynthesisError,
    SpeechSynthesisTimeout,
    SynthesizedSpeech,
)
from buddy_voice.speak_node import BuddySpeakNode
import pytest


def _script(path: Path, source: str) -> Path:
    path.write_text('#!/usr/bin/env python3\n' + source, encoding='utf-8')
    path.chmod(0o755)
    return path


def _asset(path: Path) -> Path:
    path.write_text('local test asset', encoding='utf-8')
    return path


@pytest.mark.parametrize('validator,invalid', (
    (validate_capture_seconds, (0, 31, '15', True)),
    (validate_stt_threads, (0, 4, '2', True)),
    (validate_stt_timeout_seconds, (0, 61, '30', True)),
    (validate_tts_synthesis_timeout_seconds, (0, 31, '15', True)),
    (validate_tts_playback_timeout_seconds, (0, 61, '30', True)),
))
def test_local_provider_bounds_fail_closed(validator, invalid) -> None:
    """Every documented local-provider numeric bound is validated before use."""
    for value in invalid:
        with pytest.raises(ValueError):
            validator(value)


def test_language_validation_accepts_only_profile_languages() -> None:
    assert [validate_stt_language(value) for value in ('auto', 'en', 'de')] == ['auto', 'en', 'de']
    with pytest.raises(ValueError):
        validate_stt_language('fr')


def test_pipewire_capture_uses_argv_and_removes_failed_audio(tmp_path: Path) -> None:
    """Record the exact 16kHz mono format and clean failures."""
    recorder = _script(tmp_path / 'pw-record', """
import sys, time
time.sleep(0.03)
sys.exit(7)
""")
    source = PipeWirePushToTalkAudioInput(
        record_binary=recorder, device='WH-CH520', maximum_capture_seconds=1,
        temp_directory=tmp_path)
    released = Event()
    released.set()
    with pytest.raises(Exception, match='no WAV'):
        source.capture_once(released)
    assert not list(tmp_path.glob('buddy-ptt-*.wav'))


def test_pipewire_capture_returns_valid_temporary_wav(tmp_path: Path) -> None:
    """pw-record resolving to pw-cat still selects record and stops safely."""
    pipewire_cat = _script(tmp_path / 'pw-cat', """
import json, signal, sys, time, wave
path = sys.argv[-1]
open(path + '.argv', 'w').write(json.dumps(sys.argv[1:]))
signals = []
def stop(*_):
    signals.append('TERM')
    open(path + '.signals', 'w').write(' '.join(signals))
    with wave.open(path, 'wb') as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
        output.writeframes(b'\\0\\0' * 160)
    raise SystemExit(0)
signal.signal(signal.SIGINT, lambda *_: signals.append('INT'))
signal.signal(signal.SIGTERM, stop)
while True: time.sleep(0.01)
""")
    recorder = tmp_path / 'pw-record'
    recorder.symlink_to(pipewire_cat)
    source = PipeWirePushToTalkAudioInput(
        record_binary=recorder, device='WH-CH520', maximum_capture_seconds=1,
        locale='de-DE', temp_directory=tmp_path)
    released = Event()
    worker = Thread(target=lambda: source.capture_once(released))
    worker.start()
    time.sleep(0.05)
    released.set()
    worker.join(1.0)
    capture = source.next_capture()
    assert capture is not None
    assert capture.locale == 'de-DE'
    assert capture.audio_path is not None and capture.audio_path.exists()
    assert json.loads((Path(str(capture.audio_path) + '.argv')).read_text())[:-1] == [
        '--record', '--format', 's16', '--rate', '16000', '--channels', '1', '--target', 'WH-CH520']
    assert Path(str(capture.audio_path) + '.signals').read_text() == 'INT TERM'


def test_capture_uses_private_directory_and_does_not_touch_preexisting_output(
        tmp_path: Path) -> None:
    """A preexisting output-looking symlink is never selected for PipeWire capture."""
    victim = _asset(tmp_path / 'victim.wav')
    (tmp_path / 'capture.wav').symlink_to(victim)
    recorder = _script(tmp_path / 'pw-record', """
import signal, sys, time, wave
path = sys.argv[-1]
def stop(*_):
    with wave.open(path, 'wb') as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
        output.writeframes(b'\\0\\0' * 16)
    raise SystemExit(0)
signal.signal(signal.SIGINT, stop)
while True: time.sleep(0.01)
""")
    source = PipeWirePushToTalkAudioInput(
        record_binary=recorder, maximum_capture_seconds=1, temp_directory=tmp_path)
    released = Event()
    result = []
    worker = Thread(target=lambda: result.append(source.capture_once(released)))
    worker.start()
    time.sleep(0.05)
    released.set()
    worker.join()
    capture = result[0]
    assert capture.audio_path is not None
    assert capture.audio_path.parent != tmp_path
    assert stat.S_IMODE(capture.audio_path.parent.stat().st_mode) == 0o700
    assert victim.read_text() == 'local test asset'
    private_directory = capture.audio_path.parent
    source.close()
    assert not private_directory.exists()


def test_capture_rejects_oversized_wav_and_removes_private_directory(tmp_path: Path) -> None:
    """Capture size is bounded before WAV parsing and its private directory is removed."""
    recorder = _script(tmp_path / 'pw-record', """
import sys
open(sys.argv[-1], 'wb').truncate(2 * 1024 * 1024)
""")
    source = PipeWirePushToTalkAudioInput(
        record_binary=recorder, maximum_capture_seconds=1, temp_directory=tmp_path)
    released = Event()
    failure = []

    def capture() -> None:
        try:
            source.capture_once(released)
        except Exception as error:
            failure.append(error)

    worker = Thread(target=capture)
    worker.start()
    time.sleep(0.05)
    released.set()
    worker.join()
    assert failure and 'exceeds' in str(failure[0])
    assert not list(tmp_path.glob('buddy-capture-*'))


def test_capture_settles_descendant_before_validating_mutable_output(tmp_path: Path) -> None:
    """A pw-record launcher exit cannot leave a child mutating a trusted capture."""
    recorder = _script(tmp_path / 'pw-record', """
import pathlib, signal, subprocess, sys, time, wave
output = pathlib.Path(sys.argv[-1])
marker = output.parent.parent / 'capture-descendant'
with wave.open(str(output), 'wb') as wav:
    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
    wav.writeframes(b'\\0\\0' * 16)
child = (
    'import pathlib, signal, sys, time; output = pathlib.Path(sys.argv[1]); marker = pathlib.Path(sys.argv[2]); '
    'output.write_bytes(b"mutable"); marker.with_suffix(".ready").write_text("ready"); '
    'signal.signal(signal.SIGINT, lambda *_: (marker.write_text("stopped"), sys.exit(0))); time.sleep(10)'
)
subprocess.Popen([sys.executable, '-c', child, str(output), str(marker)], close_fds=False)
deadline = time.monotonic() + 1
while not marker.with_suffix('.ready').exists() and time.monotonic() < deadline: time.sleep(.01)
""")
    source = PipeWirePushToTalkAudioInput(
        record_binary=recorder, maximum_capture_seconds=1, temp_directory=tmp_path)
    with pytest.raises(Exception, match='readable WAV'):
        source.capture_once(Event())
    assert (tmp_path / 'capture-descendant').read_text() == 'stopped'
    assert not list(tmp_path.glob('buddy-capture-*'))


def test_whisper_parses_json_and_discards_recording(tmp_path: Path) -> None:
    """whisper-cli receives an argv model/input/thread/language configuration."""
    whisper = _script(tmp_path / 'whisper-cli', """
import json, pathlib, sys
base = pathlib.Path(sys.argv[sys.argv.index('-of') + 1])
base.with_suffix('.json').write_text(json.dumps({'transcription': [{'text': ' Hallo Buddy '}] }))
pathlib.Path(sys.argv[sys.argv.index('-m') + 1]).parent.joinpath('whisper.argv').write_text(
    json.dumps(sys.argv[1:]))
""")
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = tmp_path / 'input.wav'
    import wave
    with wave.open(str(audio), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b'\\0\\0')
    from buddy_voice.providers import AudioCapture
    provider = WhisperCppSpeechToTextProvider(binary=whisper, model=model, threads=2, language='de')
    transcripts = provider.transcribe(AudioCapture(b'', 0, 'en-US', audio))
    assert transcripts[0].text == 'Hallo Buddy'
    assert transcripts[0].locale == 'de-DE'
    assert not audio.exists()
    assert not list(tmp_path.glob('input.json'))
    whisper_args = json.loads((tmp_path / 'whisper.argv').read_text())
    assert whisper_args[whisper_args.index('-t') + 1] == '2'
    assert whisper_args[whisper_args.index('-l') + 1] == 'de'


@pytest.mark.parametrize(
    ('detected_language', 'expected_locale'),
    (('en', 'en-US'), ('de', 'de-DE')),
)
def test_whisper_auto_uses_detected_result_language(
        tmp_path: Path, detected_language: str, expected_locale: str) -> None:
    """Automatic recognition supplies the English/German locale to Dialogue."""
    whisper = _script(tmp_path / 'whisper-cli', f"""
import json, pathlib, sys
base = pathlib.Path(sys.argv[sys.argv.index('-of') + 1])
base.with_suffix('.json').write_text(json.dumps({{
    'result': {{'language': '{detected_language}'}}, 'text': 'Buddy hello'}}))
""")
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = _asset(tmp_path / 'input.wav')
    from buddy_voice.providers import AudioCapture
    transcript = WhisperCppSpeechToTextProvider(
        binary=whisper, model=model, language='auto').transcribe(
            AudioCapture(b'', 0, 'en-US', audio))[0]
    assert transcript.locale == expected_locale


def test_whisper_removes_owned_capture_directory_after_handoff(tmp_path: Path) -> None:
    """STT owns the final cleanup of a private capture directory handed off by PTT."""
    whisper = _script(tmp_path / 'whisper-cli', """
import json, pathlib, sys
base = pathlib.Path(sys.argv[sys.argv.index('-of') + 1])
base.with_suffix('.json').write_text(json.dumps({'text': 'hello'}))
""")
    model = _asset(tmp_path / 'ggml-base.bin')
    capture_directory = tmp_path / 'buddy-capture-handoff'
    capture_directory.mkdir(mode=0o700)
    audio = _asset(capture_directory / 'capture.wav')
    from buddy_voice.providers import AudioCapture
    transcript = WhisperCppSpeechToTextProvider(binary=whisper, model=model).transcribe(
        AudioCapture(b'', 0, 'en-US', audio, capture_directory))[0]
    assert transcript.text == 'hello'
    assert not capture_directory.exists()


def test_noisy_whisper_child_is_drained_and_diagnostic_output_is_bounded(tmp_path: Path) -> None:
    """A noisy local child neither blocks the poll loop nor grows retained output."""
    whisper = _script(tmp_path / 'whisper-cli', """
import sys
sys.stderr.write('x' * (256 * 1024))
sys.stderr.flush()
sys.exit(7)
""")
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = _asset(tmp_path / 'input.wav')
    from buddy_voice.providers import AudioCapture
    started = time.monotonic()
    with pytest.raises(SttError, match='output truncated') as error:
        WhisperCppSpeechToTextProvider(binary=whisper, model=model).transcribe(
            AudioCapture(b'', 0, 'en-US', audio))
    assert time.monotonic() - started < 1.0
    assert len(str(error.value)) < 70 * 1024


def test_whisper_rejects_oversized_private_json_and_cleans_capture(tmp_path: Path) -> None:
    """Whisper JSON is size-bounded before decoding and never retains capture audio."""
    whisper = _script(tmp_path / 'whisper-cli', """
import pathlib, sys
base = pathlib.Path(sys.argv[sys.argv.index('-of') + 1])
base.with_suffix('.json').write_bytes(b'x' * (2 * 1024 * 1024))
""")
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = _asset(tmp_path / 'input.wav')
    from buddy_voice.providers import AudioCapture
    with pytest.raises(SttError, match='exceeds'):
        WhisperCppSpeechToTextProvider(binary=whisper, model=model).transcribe(
            AudioCapture(b'', 0, 'en-US', audio))
    assert not audio.exists()


def test_whisper_settles_descendant_before_trusting_mutable_json(tmp_path: Path) -> None:
    """A successful whisper launcher cannot leave a child changing its transcript."""
    marker = tmp_path / 'whisper-descendant'
    existing_output_directories = set(Path('/tmp').glob('buddy-whisper-*'))
    whisper = _script(tmp_path / 'whisper-cli', """
import json, pathlib, signal, subprocess, sys, time
base = pathlib.Path(sys.argv[sys.argv.index('-of') + 1])
output = base.with_suffix('.json')
output.write_text(json.dumps({'text': 'safe'}))
marker = pathlib.Path(sys.argv[sys.argv.index('-m') + 1]).parent / 'whisper-descendant'
child = (
    'import pathlib, signal, sys, time; output = pathlib.Path(sys.argv[1]); marker = pathlib.Path(sys.argv[2]); '
    'output.write_bytes(b"mutable"); marker.with_suffix(".ready").write_text("ready"); '
    'signal.signal(signal.SIGTERM, lambda *_: (marker.write_text("stopped"), sys.exit(0))); time.sleep(10)'
)
subprocess.Popen([sys.executable, '-c', child, str(output), str(marker)], close_fds=False)
deadline = time.monotonic() + 1
while not marker.with_suffix('.ready').exists() and time.monotonic() < deadline: time.sleep(.01)
""")
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = _asset(tmp_path / 'input.wav')
    from buddy_voice.providers import AudioCapture
    with pytest.raises(SttError, match='invalid JSON'):
        WhisperCppSpeechToTextProvider(binary=whisper, model=model).transcribe(
            AudioCapture(b'', 0, 'en-US', audio))
    assert marker.read_text() == 'stopped'
    assert not audio.exists()
    assert set(Path('/tmp').glob('buddy-whisper-*')) == existing_output_directories


def test_whisper_invalid_output_is_structured_and_discards_recording(tmp_path: Path) -> None:
    whisper = _script(tmp_path / 'whisper-cli', 'import sys\n')
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = _asset(tmp_path / 'input.wav')
    from buddy_voice.providers import AudioCapture
    provider = WhisperCppSpeechToTextProvider(binary=whisper, model=model)
    with pytest.raises(SttError, match='unsafe JSON'):
        provider.transcribe(AudioCapture(b'', 0, 'en-US', audio))
    assert not audio.exists()


def test_whisper_blank_audio_sentinel_fails_closed_and_discards_files(tmp_path: Path) -> None:
    """An exact normalized [BLANK_AUDIO] result is not a usable utterance."""
    whisper = _script(tmp_path / 'whisper-cli', """
import json, pathlib, sys
base = pathlib.Path(sys.argv[sys.argv.index('-of') + 1])
base.with_suffix('.json').write_text(json.dumps({'text': ' [BLANK_AUDIO] '}))
""")
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = _asset(tmp_path / 'input.wav')
    from buddy_voice.providers import AudioCapture
    provider = WhisperCppSpeechToTextProvider(binary=whisper, model=model)
    with pytest.raises(SttError, match='no usable utterance'):
        provider.transcribe(AudioCapture(b'', 0, 'en-US', audio))
    assert not audio.exists()
    assert not (tmp_path / 'input.json').exists()
    assert not _is_no_speech_sentinel('[a legitimate bracketed utterance]')


def test_whisper_timeout_terminates_child_and_discards_recording(tmp_path: Path) -> None:
    """A timed-out whisper-cli cannot retain a recording or an owned child."""
    whisper = _script(tmp_path / 'whisper-cli', 'import time\ntime.sleep(2)\n')
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = _asset(tmp_path / 'input.wav')
    from buddy_voice.providers import AudioCapture
    provider = WhisperCppSpeechToTextProvider(
        binary=whisper, model=model, timeout_seconds=1)
    with pytest.raises(SttError, match='timed out'):
        provider.transcribe(AudioCapture(b'', 0, 'en-US', audio))
    assert not audio.exists()


def test_piper_selects_locale_and_cancels_playback_with_cleanup(tmp_path: Path) -> None:
    """Synthesis and actual PipeWire playback are separate cancellable phases."""
    piper = _script(tmp_path / 'piper', """
import json, sys, wave
path = sys.argv[sys.argv.index('--output_file') + 1]
open(path + '.argv', 'w').write(json.dumps(sys.argv[1:]))
with wave.open(path, 'wb') as output:
    output.setnchannels(1); output.setsampwidth(2); output.setframerate(22050)
    output.writeframes(b'\\0\\0' * 320)
""")
    pipewire_cat = _script(tmp_path / 'pw-cat', """
import json, signal, sys, time
open(sys.argv[-1] + '.play.argv', 'w').write(json.dumps(sys.argv[1:]))
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
while True: time.sleep(0.01)
""")
    player = tmp_path / 'pw-play'
    player.symlink_to(pipewire_cat)
    en_model, en_config = _asset(tmp_path / 'en.onnx'), _asset(tmp_path / 'en.onnx.json')
    de_model, de_config = _asset(tmp_path / 'de.onnx'), _asset(tmp_path / 'de.onnx.json')
    provider = PiperTextToSpeechProvider(
        piper_binary=piper, playback_binary=player,
        english_voice=PiperVoice('en_test', 'en-US', en_model, en_config),
        german_voice=PiperVoice('de_test', 'de-DE', de_model, de_config), temp_directory=tmp_path)
    speech = provider.synthesize('Danke, das ist gut.', '', cancel_event=Event(),
                                 deadline_monotonic=time.monotonic() + 1.0)
    assert speech.audio_path is not None and speech.audio_path.exists()
    assert speech.duration_seconds == pytest.approx(320 / 22050)
    piper_args = json.loads((Path(str(speech.audio_path) + '.argv')).read_text())
    assert piper_args[piper_args.index('--model') + 1] == str(de_model)
    assert piper_args[piper_args.index('--config') + 1] == str(de_config)
    assert piper_args[piper_args.index('--output_file') + 1] == str(speech.audio_path)
    cancelled = Event()
    Thread(target=lambda: (time.sleep(0.05), cancelled.set())).start()
    with pytest.raises(SpeechPlaybackCancelled):
        provider.play(speech, cancel_event=cancelled, deadline_monotonic=time.monotonic() + 1.0)
    assert json.loads((Path(str(speech.audio_path) + '.play.argv')).read_text()) == [
        '--playback', str(speech.audio_path)]
    provider.cleanup(speech)
    assert not speech.audio_path.exists()
    with pytest.raises(Exception, match='unknown configured voice'):
        provider.synthesize('hello', 'not-configured', cancel_event=Event(),
                            deadline_monotonic=time.monotonic() + 1.0)


def test_piper_playback_deadline_is_a_structured_timeout(tmp_path: Path) -> None:
    """Playback has an independent deadline after successful synthesis."""
    piper = _script(tmp_path / 'piper', """
import sys, wave
path = sys.argv[sys.argv.index('--output_file') + 1]
with wave.open(path, 'wb') as output:
    output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
    output.writeframes(b'\\0\\0' * 160)
""")
    player = _script(tmp_path / 'pw-play', 'import time\ntime.sleep(2)\n')
    en_model, en_config = _asset(tmp_path / 'en.onnx'), _asset(tmp_path / 'en.onnx.json')
    de_model, de_config = _asset(tmp_path / 'de.onnx'), _asset(tmp_path / 'de.onnx.json')
    provider = PiperTextToSpeechProvider(
        piper_binary=piper, playback_binary=player,
        english_voice=PiperVoice('en_test', 'en-US', en_model, en_config),
        german_voice=PiperVoice('de_test', 'de-DE', de_model, de_config), temp_directory=tmp_path)
    speech = provider.synthesize(
        'hello', '', cancel_event=Event(), deadline_monotonic=time.monotonic() + 1.0)
    with pytest.raises(Exception, match='timed out'):
        provider.play(speech, cancel_event=Event(), deadline_monotonic=time.monotonic())
    provider.cleanup(speech)
    assert speech.audio_path is not None and not speech.audio_path.exists()


@pytest.mark.parametrize('unsafe_output', ('oversized', 'symlink'))
def test_piper_rejects_unsafe_output_and_removes_private_directory(
        tmp_path: Path, unsafe_output: str) -> None:
    """Piper cannot make the provider read oversized or symlinked output WAVs."""
    victim = _asset(tmp_path / 'victim.wav')
    piper = _script(tmp_path / 'piper', f"""
import os, pathlib, sys
output = pathlib.Path(sys.argv[sys.argv.index('--output_file') + 1])
victim = pathlib.Path(sys.argv[sys.argv.index('--model') + 1]).parent / 'victim.wav'
if '{unsafe_output}' == 'oversized':
    output.open('wb').truncate(9 * 1024 * 1024)
else:
    os.symlink(victim, output)
""")
    player = _script(tmp_path / 'pw-play', 'import sys\nsys.exit(0)\n')
    en_model, en_config = _asset(tmp_path / 'en.onnx'), _asset(tmp_path / 'en.onnx.json')
    de_model, de_config = _asset(tmp_path / 'de.onnx'), _asset(tmp_path / 'de.onnx.json')
    provider = PiperTextToSpeechProvider(
        piper_binary=piper, playback_binary=player,
        english_voice=PiperVoice('en_test', 'en-US', en_model, en_config),
        german_voice=PiperVoice('de_test', 'de-DE', de_model, de_config), temp_directory=tmp_path)
    with pytest.raises(Exception, match='Piper output'):
        provider.synthesize('hello', '', cancel_event=Event(), deadline_monotonic=time.monotonic() + 1.0)
    assert victim.read_text() == 'local test asset'
    assert not list(tmp_path.glob('buddy-piper-*'))


def test_piper_settles_descendant_before_trusting_mutable_wav(tmp_path: Path) -> None:
    """A Piper launcher exit cannot leave a child changing the output WAV."""
    marker = tmp_path / 'piper-descendant'
    piper = _script(tmp_path / 'piper', """
import pathlib, signal, subprocess, sys, time, wave
sys.stdin.read()
output = pathlib.Path(sys.argv[sys.argv.index('--output_file') + 1])
with wave.open(str(output), 'wb') as wav:
    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
    wav.writeframes(b'\\0\\0' * 16)
marker = pathlib.Path(sys.argv[sys.argv.index('--model') + 1]).parent / 'piper-descendant'
child = (
    'import pathlib, signal, sys, time; output = pathlib.Path(sys.argv[1]); marker = pathlib.Path(sys.argv[2]); '
    'output.write_bytes(b"mutable"); marker.with_suffix(".ready").write_text("ready"); '
    'signal.signal(signal.SIGTERM, lambda *_: (marker.write_text("stopped"), sys.exit(0))); time.sleep(10)'
)
subprocess.Popen([sys.executable, '-c', child, str(output), str(marker)], close_fds=False)
deadline = time.monotonic() + 1
while not marker.with_suffix('.ready').exists() and time.monotonic() < deadline: time.sleep(.01)
""")
    player = _script(tmp_path / 'pw-play', 'import sys\nsys.exit(0)\n')
    en_model, en_config = _asset(tmp_path / 'en.onnx'), _asset(tmp_path / 'en.onnx.json')
    de_model, de_config = _asset(tmp_path / 'de.onnx'), _asset(tmp_path / 'de.onnx.json')
    provider = PiperTextToSpeechProvider(
        piper_binary=piper, playback_binary=player,
        english_voice=PiperVoice('en_test', 'en-US', en_model, en_config),
        german_voice=PiperVoice('de_test', 'de-DE', de_model, de_config), temp_directory=tmp_path)
    with pytest.raises(SpeechSynthesisError, match='Piper output'):
        provider.synthesize('hello', '', cancel_event=Event(), deadline_monotonic=time.monotonic() + 1.0)
    assert marker.read_text() == 'stopped'
    assert not list(tmp_path.glob('buddy-piper-*'))


def test_piper_rejects_oversized_multibyte_text_before_starting_child(tmp_path: Path) -> None:
    """Speak input is limited by UTF-8 bytes before a process or temp WAV exists."""
    marker = tmp_path / 'piper-started'
    piper = _script(tmp_path / 'piper', """
import pathlib, sys
pathlib.Path(sys.argv[sys.argv.index('--model') + 1]).parent.joinpath('piper-started').write_text('started')
""")
    player = _script(tmp_path / 'pw-play', 'import sys\nsys.exit(0)\n')
    en_model, en_config = _asset(tmp_path / 'en.onnx'), _asset(tmp_path / 'en.onnx.json')
    de_model, de_config = _asset(tmp_path / 'de.onnx'), _asset(tmp_path / 'de.onnx.json')
    provider = PiperTextToSpeechProvider(
        piper_binary=piper, playback_binary=player,
        english_voice=PiperVoice('en_test', 'en-US', en_model, en_config),
        german_voice=PiperVoice('de_test', 'de-DE', de_model, de_config), temp_directory=tmp_path)
    text = '€' * (MAX_SPEECH_INPUT_UTF8_BYTES // 2)
    assert len(text.encode('utf-8')) > MAX_SPEECH_INPUT_UTF8_BYTES
    with pytest.raises(SpeechSynthesisError, match='exceeds'):
        provider.synthesize(text, '', cancel_event=Event(), deadline_monotonic=time.monotonic() + 1.0)
    assert not marker.exists()
    assert not list(tmp_path.glob('buddy-piper-*'))


def test_piper_playback_settles_descendant_after_launcher_success(tmp_path: Path) -> None:
    """Playback succeeds only after its owned descendant is stopped as well."""
    marker = tmp_path / 'playback-descendant'
    piper = _script(tmp_path / 'piper', 'import sys\nsys.exit(0)\n')
    player = _script(tmp_path / 'pw-play', """
import pathlib, signal, subprocess, sys, time
marker = pathlib.Path(sys.argv[-1]).parent / 'playback-descendant'
child = (
    'import pathlib, signal, sys, time; marker = pathlib.Path(sys.argv[1]); '
    'marker.with_suffix(".ready").write_text("ready"); '
    'signal.signal(signal.SIGTERM, lambda *_: (marker.write_text("stopped"), sys.exit(0))); time.sleep(10)'
)
subprocess.Popen([sys.executable, '-c', child, str(marker)], close_fds=False)
deadline = time.monotonic() + 1
while not marker.with_suffix('.ready').exists() and time.monotonic() < deadline: time.sleep(.01)
""")
    en_model, en_config = _asset(tmp_path / 'en.onnx'), _asset(tmp_path / 'en.onnx.json')
    de_model, de_config = _asset(tmp_path / 'de.onnx'), _asset(tmp_path / 'de.onnx.json')
    audio = _asset(tmp_path / 'speech.wav')
    provider = PiperTextToSpeechProvider(
        piper_binary=piper, playback_binary=player,
        english_voice=PiperVoice('en_test', 'en-US', en_model, en_config),
        german_voice=PiperVoice('de_test', 'de-DE', de_model, de_config), temp_directory=tmp_path)
    provider.play(
        SynthesizedSpeech(0.01, audio), cancel_event=Event(), deadline_monotonic=time.monotonic() + 1.0)
    assert marker.read_text() == 'stopped'


def test_native_child_environment_is_allowlisted(monkeypatch, tmp_path: Path) -> None:
    """Child processes receive required PipeWire variables, never arbitrary parent secrets."""
    output = tmp_path / 'environment.json'
    script = _script(tmp_path / 'environment', """
import json, os, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps(dict(os.environ)))
""")
    monkeypatch.setenv('BUDDY_PROVIDER_TEST_SECRET', 'must-not-leak')
    monkeypatch.setenv('PIPEWIRE_REMOTE', 'buddy-test-remote')
    monkeypatch.setenv('XDG_RUNTIME_DIR', '/run/user/test')
    child = _start([script, str(output)])
    while child.poll() is None:
        time.sleep(0.01)
    _finish(child)
    environment = json.loads(output.read_text())
    assert environment['PIPEWIRE_REMOTE'] == 'buddy-test-remote'
    assert environment['XDG_RUNTIME_DIR'] == '/run/user/test'
    assert environment['PATH'] == os.environ['PATH']
    assert 'BUDDY_PROVIDER_TEST_SECRET' not in environment


def test_terminate_reaps_descendants_after_provider_leader_exits(tmp_path: Path) -> None:
    """Owned process-group termination reaches a surviving child after leader exit."""
    marker = tmp_path / 'descendant-terminated'
    provider = _script(tmp_path / 'provider', """
import pathlib, subprocess, sys
marker = sys.argv[1]
child = (
    'import pathlib, signal, sys, time; '
    'pathlib.Path(sys.argv[1] + ".ready").write_text("ready"); '
    'signal.signal(signal.SIGTERM, lambda *_: (pathlib.Path(sys.argv[1]).write_text("done"), sys.exit(0))); '
    'time.sleep(10)'
)
subprocess.Popen([sys.executable, '-c', child, marker])
""")
    child = _start([provider, str(marker)])
    deadline = time.monotonic() + 1.0
    while child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert child.poll() is not None
    deadline = time.monotonic() + 1.0
    while not Path(str(marker) + '.ready').exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert Path(str(marker) + '.ready').read_text() == 'ready'
    _terminate(child)
    deadline = time.monotonic() + 1.0
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    _finish(child)
    assert marker.read_text() == 'done'


@pytest.mark.parametrize(
    ('cancel_after_seconds', 'deadline_offset_seconds', 'expected_error'),
    ((0.05, 1.0, SpeechSynthesisCancelled), (None, 0.05, SpeechSynthesisTimeout)),
)
def test_piper_nonreading_maximum_stdin_is_cancellable_and_cleans_temp_audio(
        tmp_path: Path,
        cancel_after_seconds: float | None,
        deadline_offset_seconds: float,
        expected_error: type[Exception]) -> None:
    """Maximum valid text cannot block Piper cancellation, timeout, or cleanup."""
    piper = _script(tmp_path / 'piper', """
import pathlib, signal, sys, time
output = sys.argv[sys.argv.index('--output_file') + 1]
marker = pathlib.Path(sys.argv[sys.argv.index('--model') + 1]).parent / 'terminated'
def stop(*_):
    marker.write_text('terminated')
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
while True: time.sleep(0.01)
""")
    player = _script(tmp_path / 'pw-play', 'import sys\nsys.exit(0)\n')
    en_model, en_config = _asset(tmp_path / 'en.onnx'), _asset(tmp_path / 'en.onnx.json')
    de_model, de_config = _asset(tmp_path / 'de.onnx'), _asset(tmp_path / 'de.onnx.json')
    provider = PiperTextToSpeechProvider(
        piper_binary=piper, playback_binary=player,
        english_voice=PiperVoice('en_test', 'en-US', en_model, en_config),
        german_voice=PiperVoice('de_test', 'de-DE', de_model, de_config), temp_directory=tmp_path)
    cancelled = Event()
    trigger = None
    if cancel_after_seconds is not None:
        trigger = Thread(target=lambda: (time.sleep(cancel_after_seconds), cancelled.set()))
        trigger.start()
    started = time.monotonic()
    with pytest.raises(expected_error):
        provider.synthesize(
            'x' * MAX_SPEECH_INPUT_UTF8_BYTES,
            '',
            cancel_event=cancelled,
            deadline_monotonic=time.monotonic() + deadline_offset_seconds,
        )
    if trigger is not None:
        trigger.join()
    assert time.monotonic() - started < 0.6
    assert not list(tmp_path.glob('buddy-piper-*.wav'))
    assert (tmp_path / 'terminated').read_text() == 'terminated'


def test_missing_local_assets_fail_closed_and_wakeword_stays_disabled(tmp_path: Path) -> None:
    """No implicit download, alternate phrase, or third-party runtime is used."""
    with pytest.raises(LocalProviderError, match='unavailable'):
        WhisperCppSpeechToTextProvider(binary=tmp_path / 'missing', model=tmp_path / 'model')
    wake = OptionalWakeWordProvider()
    assert not wake.available
    assert not wake.detected(b'Buddy')


def test_speak_action_only_succeeds_after_native_playback_and_cleanup(tmp_path: Path) -> None:
    """The action does not turn successful synthesis into premature success."""
    wav = _asset(tmp_path / 'speech.wav')

    class RealProvider:
        """Records the native synthesis/playback/cleanup ordering."""

        def __init__(self) -> None:
            self.calls: list[str] = []

        def synthesize(self, text, voice, *, cancel_event, deadline_monotonic):
            self.calls.append('synthesize')
            return SynthesizedSpeech(0.01, wav)

        def play(self, speech, *, cancel_event, deadline_monotonic):
            self.calls.append('play')

        def cleanup(self, speech):
            self.calls.append('cleanup')
            speech.audio_path.unlink()

    class Goal:
        """Minimal frozen action-handle behavior for the direct component boundary."""

        def __init__(self) -> None:
            self.request = type('Request', (), {'text': 'hello', 'voice': ''})()
            self.is_cancel_requested = False
            self.feedback = []
            self.succeeded = False

        def publish_feedback(self, value):
            self.feedback.append(value)

        def succeed(self):
            self.succeeded = True

    provider = RealProvider()
    node = object.__new__(BuddySpeakNode)
    node._text_to_speech = provider
    node._synthesis_timeout_seconds = 1.0
    node._playback_timeout_seconds = 1.0
    goal = Goal()
    result = node._execute_active(goal, Event())
    assert goal.succeeded
    assert result.message == 'speech playback completed'
    assert provider.calls == ['synthesize', 'play', 'cleanup']
    assert goal.feedback[-1].progress == 1.0
    assert not wav.exists()


def test_unexpected_native_playback_error_is_an_aborted_action_with_cleanup(
        tmp_path: Path) -> None:
    """Unexpected playback failures remain structured action/diagnostic failures."""
    wav = _asset(tmp_path / 'speech.wav')

    class Provider:
        """Produces native audio then raises an untyped playback exception."""

        def synthesize(self, text, voice, *, cancel_event, deadline_monotonic):
            return SynthesizedSpeech(0.01, wav)

        def play(self, speech, *, cancel_event, deadline_monotonic):
            raise RuntimeError('player crashed')

        def cleanup(self, speech):
            speech.audio_path.unlink()

    class Goal:
        """Records frozen action terminal state and feedback."""

        def __init__(self) -> None:
            self.request = type('Request', (), {'text': 'hello', 'voice': ''})()
            self.is_cancel_requested = False
            self.aborted = False

        def publish_feedback(self, value):
            pass

        def abort(self):
            self.aborted = True

    diagnostics = []
    node = object.__new__(BuddySpeakNode)
    node._text_to_speech = Provider()
    node._synthesis_timeout_seconds = 1.0
    node._playback_timeout_seconds = 1.0
    node._publish_failure_diagnostic = lambda code, message: diagnostics.append((code, message))
    goal = Goal()
    result = node._execute_active(goal, Event())
    assert goal.aborted
    assert result.outcome == result.OUTCOME_FAILED
    assert 'unexpected speech playback failure: player crashed' in result.message
    assert diagnostics and diagnostics[0][0] == 1004
    assert not wav.exists()
