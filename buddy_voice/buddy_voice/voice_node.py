"""ROS component that publishes recognized utterances and voice emergency stops."""

from __future__ import annotations

import uuid

from buddy_interfaces.msg import EmergencyStopRequest, RecognizedUtterance
from builtin_interfaces.msg import Time
import rclpy
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
        poll_period = self.get_parameter('capture_poll_period_seconds').value
        self._capture_timer = self.create_timer(float(poll_period), self.process_next_capture)

    def process_next_capture(self) -> int:
        """Process one completed capture and return published transcript count."""
        capture = self._audio_input.next_capture()
        if capture is None:
            return 0
        transcripts = self._speech_to_text.transcribe(capture)
        for transcript in transcripts:
            self._publish_transcript(transcript, capture.input_mode)
        return len(transcripts)

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
    node = BuddyVoiceNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
