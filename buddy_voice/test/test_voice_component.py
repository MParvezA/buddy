"""ROS component tests for utterance and direct spoken-stop publication."""

import time

from buddy_interfaces.msg import EmergencyStopRequest, RecognizedUtterance
from buddy_voice.providers import FakeAudioInput, FakeSpeechToTextProvider, Transcript
from buddy_voice.voice_node import (
    BuddyVoiceNode,
    EMERGENCY_STOP_TOPIC,
    UTTERANCE_TOPIC,
    voice_event_qos,
)
import rclpy
from rclpy.executors import SingleThreadedExecutor


def _spin_until(executor: SingleThreadedExecutor, predicate: object) -> bool:
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.05)
        if predicate():
            return True
    return False


def test_voice_component_publishes_interim_final_and_direct_stop() -> None:
    """A final bounded stop phrase reaches safety without a dialogue dependency."""
    rclpy.init()
    audio = FakeAudioInput()
    stt = FakeSpeechToTextProvider([[
        Transcript('sto', 0.4, False),
        Transcript('Buddy, stop!', 0.99, True),
    ]])
    voice = BuddyVoiceNode(audio, stt)
    observer = rclpy.create_node('voice_component_observer')
    utterances: list[RecognizedUtterance] = []
    stops: list[EmergencyStopRequest] = []
    observer.create_subscription(
        RecognizedUtterance, UTTERANCE_TOPIC, utterances.append, voice_event_qos())
    observer.create_subscription(
        EmergencyStopRequest, EMERGENCY_STOP_TOPIC, stops.append, voice_event_qos())
    executor = SingleThreadedExecutor()
    executor.add_node(voice)
    executor.add_node(observer)
    try:
        audio.submit()
        assert voice.process_next_capture() == 2
        assert _spin_until(executor, lambda: len(utterances) == 2 and len(stops) == 1)
        assert [message.text for message in utterances] == ['sto', 'Buddy, stop!']
        assert [message.is_final for message in utterances] == [False, True]
        assert utterances[1].input_mode == RecognizedUtterance.INPUT_PUSH_TO_TALK
        assert tuple(utterances[0].utterance_id.uuid) != tuple(utterances[1].utterance_id.uuid)
        assert any(utterances[1].utterance_id.uuid)
        assert stops[0].reason_code == EmergencyStopRequest.REASON_VOICE_COMMAND
        assert stops[0].source == 'buddy_voice.spoken_stop_detector'
        assert tuple(stops[0].request_id.uuid) != tuple(utterances[1].utterance_id.uuid)
        assert any(stops[0].request_id.uuid)
    finally:
        executor.remove_node(observer)
        executor.remove_node(voice)
        observer.destroy_node()
        voice.destroy_node()
        rclpy.shutdown()


def test_voice_component_does_not_stop_for_substring() -> None:
    """A phrase such as desktop is published as speech but never as a stop event."""
    rclpy.init()
    audio = FakeAudioInput()
    stt = FakeSpeechToTextProvider([[Transcript('desktop', 0.99, True)]])
    voice = BuddyVoiceNode(audio, stt)
    observer = rclpy.create_node('voice_negative_observer')
    stops: list[EmergencyStopRequest] = []
    observer.create_subscription(
        EmergencyStopRequest, EMERGENCY_STOP_TOPIC, stops.append, voice_event_qos())
    executor = SingleThreadedExecutor()
    executor.add_node(voice)
    executor.add_node(observer)
    try:
        audio.submit()
        voice.process_next_capture()
        for _ in range(4):
            executor.spin_once(timeout_sec=0.03)
        assert stops == []
    finally:
        executor.remove_node(observer)
        executor.remove_node(voice)
        observer.destroy_node()
        voice.destroy_node()
        rclpy.shutdown()
