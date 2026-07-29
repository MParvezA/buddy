"""Deterministic provider-failure diagnostics for the voice input boundary."""

from buddy_voice.providers import FakeAudioInput, FakeSpeechToTextProvider, Transcript
from buddy_voice.voice_node import BuddyVoiceNode, DIAGNOSTIC_NAME, validate_capture_poll_period
from diagnostic_msgs.msg import DiagnosticStatus
import pytest
import rclpy


class _Recorder:
    """Small publisher substitute that exposes side effects to unit tests."""

    def __init__(self) -> None:
        self.messages = []

    def publish(self, message) -> None:
        self.messages.append(message)


class _FailOnceAudioInput(FakeAudioInput):
    """Raise once, then provide queued test audio normally."""

    def __init__(self) -> None:
        super().__init__()
        self._fail_next = True

    def next_capture(self):
        if self._fail_next:
            self._fail_next = False
            raise RuntimeError('microphone disconnected')
        return super().next_capture()


class _FailOnceSpeechToText(FakeSpeechToTextProvider):
    """Raise once, then return the configured deterministic transcript batch."""

    def __init__(self) -> None:
        super().__init__([[Transcript('hello buddy', 0.99, True)]])
        self._fail_next = True

    def transcribe(self, capture):
        if self._fail_next:
            self._fail_next = False
            raise RuntimeError('local model unavailable')
        return super().transcribe(capture)


@pytest.fixture
def initialized_rclpy():
    """Provide an isolated ROS client lifecycle for each component test."""
    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()


def _diagnostic_values(message):
    return {value.key: value.value for value in message.status[0].values}


def _install_recorders(node):
    diagnostics = _Recorder()
    utterances = _Recorder()
    stops = _Recorder()
    node._diagnostics_publisher = diagnostics
    node.utterance_publisher = utterances
    node.emergency_stop_publisher = stops
    return diagnostics, utterances, stops


def test_voice_input_startup_reports_provider_identity_and_ok(initialized_rclpy) -> None:
    """The periodic status starts healthy and identifies both local boundaries."""
    voice = BuddyVoiceNode(FakeAudioInput(), FakeSpeechToTextProvider())
    diagnostics, _, _ = _install_recorders(voice)
    try:
        voice._publish_diagnostic()
        status = diagnostics.messages[-1].status[0]
        values = _diagnostic_values(diagnostics.messages[-1])

        assert status.name == DIAGNOSTIC_NAME
        assert status.hardware_id == 'local_voice'
        assert status.level == DiagnosticStatus.OK
        assert status.message == 'voice input providers ready'
        assert values['audio_input_provider'] == 'FakeAudioInput'
        assert values['speech_to_text_provider'] == 'FakeSpeechToTextProvider'
        assert values['audio_input_ready'] == 'true'
        assert values['speech_to_text_ready'] == 'true'
        assert values['last_error_source'] == ''
    finally:
        voice.destroy_node()


def test_audio_provider_exception_is_diagnostic_and_recovers(initialized_rclpy) -> None:
    """Audio failure neither kills polling nor produces an utterance or stop request."""
    audio = _FailOnceAudioInput()
    voice = BuddyVoiceNode(
        audio, FakeSpeechToTextProvider([[Transcript('hello', 0.99, True)]]))
    diagnostics, utterances, stops = _install_recorders(voice)
    try:
        assert voice.process_next_capture() == 0
        failure = diagnostics.messages[-1].status[0]
        failure_values = _diagnostic_values(diagnostics.messages[-1])
        assert failure.level == DiagnosticStatus.ERROR
        assert failure.message == 'audio_input provider failure'
        assert failure_values['audio_input_ready'] == 'false'
        assert failure_values['speech_to_text_ready'] == 'true'
        assert failure_values['last_error_source'] == 'audio_input'
        assert failure_values['last_error_type'] == 'RuntimeError'
        assert failure_values['last_error_message'] == 'microphone disconnected'
        assert utterances.messages == []
        assert stops.messages == []

        audio.submit()
        assert voice.process_next_capture() == 1
        recovery = diagnostics.messages[-1].status[0]
        recovery_values = _diagnostic_values(diagnostics.messages[-1])
        assert recovery.level == DiagnosticStatus.OK
        assert recovery_values['audio_input_ready'] == 'true'
        assert recovery_values['speech_to_text_ready'] == 'true'
        assert recovery_values['last_error_source'] == ''
        assert [message.text for message in utterances.messages] == ['hello']
        assert stops.messages == []
    finally:
        voice.destroy_node()


def test_stt_provider_exception_is_diagnostic_and_recovers(initialized_rclpy) -> None:
    """STT failures are contained locally and cannot synthesize an emergency event."""
    audio = FakeAudioInput()
    stt = _FailOnceSpeechToText()
    voice = BuddyVoiceNode(audio, stt)
    diagnostics, utterances, stops = _install_recorders(voice)
    try:
        audio.submit()
        assert voice.process_next_capture() == 0
        failure = diagnostics.messages[-1].status[0]
        failure_values = _diagnostic_values(diagnostics.messages[-1])
        assert failure.level == DiagnosticStatus.ERROR
        assert failure.message == 'speech_to_text provider failure'
        assert failure_values['audio_input_ready'] == 'true'
        assert failure_values['speech_to_text_ready'] == 'false'
        assert failure_values['last_error_source'] == 'speech_to_text'
        assert failure_values['last_error_type'] == 'RuntimeError'
        assert failure_values['last_error_message'] == 'local model unavailable'
        assert utterances.messages == []
        assert stops.messages == []

        audio.submit()
        assert voice.process_next_capture() == 1
        recovery = diagnostics.messages[-1].status[0]
        recovery_values = _diagnostic_values(diagnostics.messages[-1])
        assert recovery.level == DiagnosticStatus.OK
        assert recovery_values['audio_input_ready'] == 'true'
        assert recovery_values['speech_to_text_ready'] == 'true'
        assert recovery_values['last_error_type'] == ''
        assert [message.text for message in utterances.messages] == ['hello buddy']
        assert stops.messages == []
    finally:
        voice.destroy_node()


def test_terminal_capture_failure_uses_public_diagnostic_boundary(initialized_rclpy) -> None:
    """A terminal PTT exception publishes an error without voice or stop output."""
    voice = BuddyVoiceNode(FakeAudioInput(), FakeSpeechToTextProvider())
    diagnostics, utterances, stops = _install_recorders(voice)
    try:
        voice.report_provider_failure('audio_input', RuntimeError('device unavailable'))
        status = diagnostics.messages[-1].status[0]
        values = _diagnostic_values(diagnostics.messages[-1])
        assert status.level == DiagnosticStatus.ERROR
        assert status.message == 'audio_input provider failure'
        assert values['last_error_message'] == 'device unavailable'
        assert utterances.messages == []
        assert stops.messages == []
    finally:
        voice.destroy_node()


@pytest.mark.parametrize('value', (0, -0.01, float('inf'), float('nan'), 'invalid'))
def test_capture_poll_period_must_be_positive_and_finite(value) -> None:
    """Invalid polling periods are rejected before a ROS timer can be created."""
    with pytest.raises(ValueError, match='capture_poll_period_seconds'):
        validate_capture_poll_period(value)


def test_capture_poll_period_accepts_positive_finite_values() -> None:
    """Valid period values remain usable after strict validation."""
    assert validate_capture_poll_period('0.05') == 0.05
