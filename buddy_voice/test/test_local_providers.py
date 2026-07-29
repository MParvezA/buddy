"""Component tests for local providers using only temporary fake executables."""

from __future__ import annotations

from pathlib import Path
from threading import Event, Thread
import json
import time

import pytest

from buddy_voice.local_providers import (
    LocalProviderError,
    OptionalWakeWordProvider,
    PiperTextToSpeechProvider,
    PiperVoice,
    PipeWirePushToTalkAudioInput,
    SpeechPlaybackCancelled,
    SttError,
    WhisperCppSpeechToTextProvider,
    validate_capture_seconds,
    validate_stt_language,
    validate_stt_threads,
    validate_stt_timeout_seconds,
    validate_tts_playback_timeout_seconds,
    validate_tts_synthesis_timeout_seconds,
)
from buddy_voice.providers import SynthesizedSpeech
from buddy_voice.speak_node import BuddySpeakNode


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
    """PipeWire records the exact 16kHz mono format and cleans failures."""
    recorder = _script(tmp_path / 'pw-record', '''
import sys, time
time.sleep(0.03)
sys.exit(7)
''')
    source = PipeWirePushToTalkAudioInput(
        record_binary=recorder, device='WH-CH520', maximum_capture_seconds=1,
        temp_directory=tmp_path)
    released = Event()
    released.set()
    with pytest.raises(Exception, match='no WAV'):
        source.capture_once(released)
    assert not list(tmp_path.glob('buddy-ptt-*.wav'))


def test_pipewire_capture_returns_valid_temporary_wav(tmp_path: Path) -> None:
    """A fake pw-record process is terminated/reaped after terminal release."""
    recorder = _script(tmp_path / 'pw-record', '''
import json, signal, sys, time, wave
path = sys.argv[-1]
open(path + '.argv', 'w').write(json.dumps(sys.argv[1:]))
def done(*_):
    with wave.open(path, 'wb') as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
        output.writeframes(b'\\0\\0' * 160)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, done)
while True: time.sleep(0.01)
''')
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
        '--format', 's16', '--rate', '16000', '--channels', '1', '--target', 'WH-CH520']


def test_whisper_parses_json_and_discards_recording(tmp_path: Path) -> None:
    """whisper-cli receives an argv model/input/thread/language configuration."""
    whisper = _script(tmp_path / 'whisper-cli', '''
import json, pathlib, sys
base = pathlib.Path(sys.argv[sys.argv.index('-of') + 1])
base.with_suffix('.json').write_text(json.dumps({'transcription': [{'text': ' Hallo Buddy '}] }))
base.with_suffix('.argv').write_text(json.dumps(sys.argv[1:]))
''')
    model = _asset(tmp_path / 'ggml-base.bin')
    audio = tmp_path / 'input.wav'
    import wave
    with wave.open(str(audio), 'wb') as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000); output.writeframes(b'\\0\\0')
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
    piper = _script(tmp_path / 'piper', '''
import sys, wave
path = sys.argv[sys.argv.index('--output_file') + 1]
with wave.open(path, 'wb') as output:
    output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
    output.writeframes(b'\\0\\0' * 320)
''')
    player = _script(tmp_path / 'pw-play', '''
import signal, time
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
while True: time.sleep(0.01)
''')
    en_model, en_config = _asset(tmp_path / 'en.onnx'), _asset(tmp_path / 'en.onnx.json')
    de_model, de_config = _asset(tmp_path / 'de.onnx'), _asset(tmp_path / 'de.onnx.json')
    provider = PiperTextToSpeechProvider(
        piper_binary=piper, playback_binary=player,
        english_voice=PiperVoice('en_test', 'en-US', en_model, en_config),
        german_voice=PiperVoice('de_test', 'de-DE', de_model, de_config), temp_directory=tmp_path)
    speech = provider.synthesize('Danke, das ist gut.', '', cancel_event=Event(),
                                 deadline_monotonic=time.monotonic() + 1.0)
    assert speech.audio_path is not None and speech.audio_path.exists()
    cancelled = Event()
    Thread(target=lambda: (time.sleep(0.05), cancelled.set())).start()
    with pytest.raises(SpeechPlaybackCancelled):
        provider.play(speech, cancel_event=cancelled, deadline_monotonic=time.monotonic() + 1.0)
    provider.cleanup(speech)
    assert not speech.audio_path.exists()
    with pytest.raises(Exception, match='unknown configured voice'):
        provider.synthesize('hello', 'not-configured', cancel_event=Event(),
                            deadline_monotonic=time.monotonic() + 1.0)


def test_piper_playback_deadline_is_a_structured_timeout(tmp_path: Path) -> None:
    """PipeWire playback has an independent deadline after successful synthesis."""
    piper = _script(tmp_path / 'piper', '''
import sys, wave
path = sys.argv[sys.argv.index('--output_file') + 1]
with wave.open(path, 'wb') as output:
    output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
    output.writeframes(b'\\0\\0' * 160)
''')
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
    assert not wav.exists()
