"""Pure deterministic tests for the replaceable voice provider layer."""

from buddy_voice.emergency import is_emergency_stop_phrase, normalize_spoken_phrase
from buddy_voice.providers import (
    FakeAudioInput,
    FakeSpeechToTextProvider,
    FakeTextToSpeechProvider,
    Transcript,
)


def test_push_to_talk_and_fake_stt_are_ordered() -> None:
    """Completed push-to-talk captures feed preconfigured transcript batches."""
    audio = FakeAudioInput()
    recognizer = FakeSpeechToTextProvider([[Transcript('hello', 0.9, True)]])
    audio.submit(b'first', 'en-GB')
    capture = audio.next_capture()

    assert capture is not None
    assert capture.samples == b'first'
    assert capture.input_mode == 0
    assert recognizer.transcribe(capture) == [Transcript('hello', 0.9, True)]
    assert recognizer.captures == [capture]


def test_fake_tts_is_deterministic() -> None:
    """The fake TTS reports fixed duration and records its local request."""
    tts = FakeTextToSpeechProvider(duration_seconds=0.25)

    assert tts.synthesize('hello', 'calm').duration_seconds == 0.25
    assert tts.requests == [('hello', 'calm')]


def test_stop_detector_matches_complete_normalized_phrases() -> None:
    """Punctuation/case normalize, but stop tokens never match substrings."""
    assert normalize_spoken_phrase(' Buddy, STOP! ') == 'buddy stop'
    assert is_emergency_stop_phrase(' Buddy, STOP! ')
    assert is_emergency_stop_phrase('emergency stop')
    assert not is_emergency_stop_phrase('desktop')
    assert not is_emergency_stop_phrase('stoplight')
    assert not is_emergency_stop_phrase('please stop the music')
