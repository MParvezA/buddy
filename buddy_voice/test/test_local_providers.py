"""Component tests for local providers using only temporary fake executables."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Thread
import time

from buddy_voice.local_providers import (
    LocalProviderError,
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
from buddy_voice.providers import SynthesizedSpeech
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


def test_whisper_parses_json_and_discards_recording(tmp_path: Path) -> None:
    """whisper-cli receives an argv model/input/thread/language configuration."""
    whisper = _script(tmp_path / 'whisper-cli', """
import json, pathlib, sys
base = pathlib.Path(sys.argv[sys.argv.index('-of') + 1])
base.with_suffix('.json').write_text(json.dumps({'transcription': [{'text': ' Hallo Buddy '}] }))
base.with_suffix('.argv').write_text(json.dumps(sys.argv[1:]))
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
    whisper_args = json.loads((tmp_path / 'input.argv').read_text())
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


def test_whisper_invalid_output_is_structured_and_discards_recording(tmp_path: Path) -> None:
    whisper = _script(tmp_path / 'whisper-cli', 'import sys\n')
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = _asset(tmp_path / 'input.wav')
    from buddy_voice.providers import AudioCapture
    provider = WhisperCppSpeechToTextProvider(binary=whisper, model=model)
    with pytest.raises(SttError, match='invalid JSON'):
        provider.transcribe(AudioCapture(b'', 0, 'en-US', audio))
    assert not audio.exists()


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
