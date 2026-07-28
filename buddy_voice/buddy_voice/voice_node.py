"""ROS component that publishes recognized utterances and voice emergency stops."""

from __future__ import annotations

import math
import uuid

from buddy_interfaces.msg import EmergencyStopRequest, RecognizedUtterance
from builtin_interfaces.msg import Time
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from .emergency import is_emergency_stop_phrase
from .providers import (
    AudioInputProvider,
    FakeSpeechToTextProvider,
    PushToTalkAudioInput,
    SpeechToTextProvider,
    Transcript,
)


UTTERANCE_TOPIC = '/buddy/voice/utterance'
EMERGENCY_STOP_TOPIC = '/buddy/safety/emergency_stop/request'
DIAGNOSTICS_TOPIC = '/diagnostics'
DIAGNOSTIC_NAME = 'buddy_voice/voice_input'


def voice_event_qos() -> QoSProfile:
    """Return the frozen reliable, volatile, depth-10 event QoS."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )


def _uuid_message(value: uuid.UUID) -> list[int]:
    """Return UUID bytes in the generated ROS field representation."""
    return list(value.bytes)


def validate_capture_poll_period(value: object) -> float:
    """Return a safe capture period or reject an invalid timer configuration."""
    try:
        period = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError('capture_poll_period_seconds must be a number') from error
    if not math.isfinite(period) or period <= 0.0:
        raise ValueError(
            'capture_poll_period_seconds must be finite and greater than zero')
    return period


class BuddyVoiceNode(Node):
    """Bridges completed local audio captures into frozen voice interfaces."""

    def __init__(
            self,
            audio_input: AudioInputProvider | None = None,
            speech_to_text: SpeechToTextProvider | None = None,
            *,
            node_name: str = 'voice_input') -> None:
        super().__init__(node_name, namespace='/buddy')
        if not self.has_parameter('use_sim_time'):
            self.declare_parameter('use_sim_time', False)
        self._audio_input = audio_input or PushToTalkAudioInput()
        self._speech_to_text = speech_to_text or FakeSpeechToTextProvider()
        self.declare_parameter('capture_poll_period_seconds', 0.05)
        self.utterance_publisher = self.create_publisher(
            RecognizedUtterance, UTTERANCE_TOPIC, voice_event_qos())
        self.emergency_stop_publisher = self.create_publisher(
            EmergencyStopRequest, EMERGENCY_STOP_TOPIC, voice_event_qos())
        self._diagnostics_publisher = self.create_publisher(
            DiagnosticArray, DIAGNOSTICS_TOPIC, voice_event_qos())
        self._audio_ready = True
        self._speech_to_text_ready = True
        self._last_error_source = ''
        self._last_error_type = ''
        self._last_error_message = ''
        poll_period = validate_capture_poll_period(
            self.get_parameter('capture_poll_period_seconds').value)
        self._publish_diagnostic()
        self._capture_timer = self.create_timer(poll_period, self.process_next_capture)

    def process_next_capture(self) -> int:
        """Process one completed capture and return published transcript count."""
        try:
            capture = self._audio_input.next_capture()
        except Exception as error:  # Provider failures must not kill the timer.
            self._record_provider_error('audio_input', error)
            return 0
        if capture is None:
            self._publish_diagnostic()
            return 0
        self._audio_ready = True
        try:
            transcripts = self._speech_to_text.transcribe(capture)
        except Exception as error:  # Provider failures must not publish fake speech.
            self._record_provider_error('speech_to_text', error)
            return 0
        self._speech_to_text_ready = True
        self._clear_provider_error()
        for transcript in transcripts:
            self._publish_transcript(transcript, capture.input_mode)
        self._publish_diagnostic()
        return len(transcripts)

    def _record_provider_error(self, source: str, error: Exception) -> None:
        """Retain structured failure state and report it without propagation."""
        if source == 'audio_input':
            self._audio_ready = False
        else:
            self._speech_to_text_ready = False
        self._last_error_source = source
        self._last_error_type = type(error).__name__
        self._last_error_message = str(error) or 'provider raised without a message'
        self.get_logger().error(
            f'{source} provider failed: {self._last_error_type}: '
            f'{self._last_error_message}')
        self._publish_diagnostic()

    def _clear_provider_error(self) -> None:
        """Restore the readiness state after a complete successful capture."""
        self._audio_ready = True
        self._speech_to_text_ready = True
        self._last_error_source = ''
        self._last_error_type = ''
        self._last_error_message = ''

    def _publish_diagnostic(self) -> None:
        """Publish periodic local-provider readiness on the frozen diagnostics topic."""
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = DIAGNOSTIC_NAME
        status.hardware_id = 'local_voice'
        status.level = (
            DiagnosticStatus.OK
            if self._audio_ready and self._speech_to_text_ready
            else DiagnosticStatus.ERROR
        )
        status.message = (
            'voice input providers ready'
            if status.level == DiagnosticStatus.OK
            else f'{self._last_error_source} provider failure'
        )
        status.values = [
            KeyValue(key='audio_input_provider',
                     value=type(self._audio_input).__name__),
            KeyValue(key='speech_to_text_provider',
                     value=type(self._speech_to_text).__name__),
            KeyValue(key='audio_input_ready', value=str(self._audio_ready).lower()),
            KeyValue(key='speech_to_text_ready',
                     value=str(self._speech_to_text_ready).lower()),
            KeyValue(key='last_error_source', value=self._last_error_source),
            KeyValue(key='last_error_type', value=self._last_error_type),
            KeyValue(key='last_error_message', value=self._last_error_message),
        ]
        array.status = [status]
        self._diagnostics_publisher.publish(array)

    def submit_push_to_talk_audio(self, samples: bytes, locale: str = 'en-US') -> None:
        """Accept one completed push-to-talk capture on the initial local path."""
        if not isinstance(self._audio_input, PushToTalkAudioInput):
            raise RuntimeError('configured audio provider is not push-to-talk capable')
        self._audio_input.push_completed_capture(samples, locale)

    def _publish_transcript(self, transcript: Transcript, input_mode: int) -> None:
        utterance = RecognizedUtterance()
        utterance.header.stamp = self.get_clock().now().to_msg()
        utterance.header.frame_id = ''
        utterance.utterance_id.uuid = _uuid_message(uuid.uuid4())
        utterance.text = transcript.text
        utterance.locale = transcript.locale
        utterance.confidence = transcript.confidence
        utterance.is_final = transcript.is_final
        utterance.input_mode = input_mode

        if transcript.is_final and is_emergency_stop_phrase(transcript.text):
            self._publish_emergency_stop(transcript.text, utterance.header.stamp)
        self.utterance_publisher.publish(utterance)

    def _publish_emergency_stop(self, text: str, stamp: Time) -> None:
        request = EmergencyStopRequest()
        request.header.stamp = stamp
        request.header.frame_id = ''
        request.request_id.uuid = _uuid_message(uuid.uuid4())
        request.source = 'buddy_voice.spoken_stop_detector'
        request.reason_code = EmergencyStopRequest.REASON_VOICE_COMMAND
        request.reason = text
        self.emergency_stop_publisher.publish(request)


def main(args: list[str] | None = None) -> None:
    """Run the local push-to-talk voice input node."""
    rclpy.init(args=args)
    node = None
    try:
        node = BuddyVoiceNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
