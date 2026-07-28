"""ROS action tests for Speak success, cancellation, and provider failures."""

from concurrent.futures import ThreadPoolExecutor
import time

from buddy_interfaces.action import Speak
from buddy_voice.providers import FakeTextToSpeechProvider
from buddy_voice.speak_node import BuddySpeakNode, SPEAK_ACTION
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor


def _future_result(future: object, timeout: float = 2.0) -> object:
    """Wait for an rclpy future, whose result method has no timeout argument."""
    deadline = time.monotonic() + timeout
    while not future.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert future.done(), 'ROS future did not complete before its test timeout'
    return future.result()


class SpeakHarness:
    """Owns an isolated action server/client pair for deterministic component tests."""

    def __init__(
            self,
            provider: FakeTextToSpeechProvider,
            *,
            steps: int = 3,
            delay: float = 0.01) -> None:
        rclpy.init()
        self.server = BuddySpeakNode(provider, playback_steps=steps, step_seconds=delay)
        self.client_node = rclpy.create_node('speak_component_client')
        self.client = ActionClient(self.client_node, Speak, SPEAK_ACTION)
        self.executor = MultiThreadedExecutor(num_threads=4)
        self.executor.add_node(self.server)
        self.executor.add_node(self.client_node)
        self.thread = ThreadPoolExecutor(max_workers=1)
        self.thread.submit(self.executor.spin)
        assert self.client.wait_for_server(timeout_sec=2.0)

    def close(self) -> None:
        """Stop ROS execution and clean up the action client/server."""
        self.executor.shutdown()
        self.thread.shutdown(wait=True)
        self.client.destroy()
        self.client_node.destroy_node()
        self.server.destroy_node()
        rclpy.shutdown()

    def send(self, text: str, feedback: list[Speak.Feedback] | None = None) -> object:
        """Send a minimal frozen Speak goal and return its accepted handle."""
        goal = Speak.Goal()
        goal.text = text
        future = self.client.send_goal_async(
            goal,
            feedback_callback=(
                lambda message: feedback.append(message.feedback)
            ) if feedback is not None else None,
        )
        return _future_result(future)


def test_speak_action_succeeds_with_feedback() -> None:
    """Mock playback returns structured success and all expected action states."""
    harness = SpeakHarness(FakeTextToSpeechProvider(duration_seconds=0.25))
    feedback: list[Speak.Feedback] = []
    try:
        handle = harness.send('hello', feedback)
        result = _future_result(handle.get_result_async())
        assert result.result.outcome == Speak.Result.OUTCOME_SUCCEEDED
        assert result.result.audio_duration.sec == 0
        assert result.result.audio_duration.nanosec == 250_000_000
        assert [item.state for item in feedback] == [
            Speak.Feedback.STATE_QUEUED,
            Speak.Feedback.STATE_SYNTHESIZING,
            Speak.Feedback.STATE_SPEAKING,
            Speak.Feedback.STATE_SPEAKING,
            Speak.Feedback.STATE_SPEAKING,
        ]
    finally:
        harness.close()


def test_speak_action_can_be_cancelled() -> None:
    """Cancellation interrupts mock playback and returns the frozen outcome."""
    harness = SpeakHarness(FakeTextToSpeechProvider(), steps=20, delay=0.02)
    try:
        handle = harness.send('long message')
        time.sleep(0.05)
        assert _future_result(handle.cancel_goal_async()).goals_canceling
        result = _future_result(handle.get_result_async())
        assert result.result.outcome == Speak.Result.OUTCOME_CANCELLED
    finally:
        harness.close()


def test_speak_action_reports_provider_failure() -> None:
    """A provider failure aborts with a structured failed action result."""
    harness = SpeakHarness(FakeTextToSpeechProvider(fail_for={'unavailable'}))
    try:
        handle = harness.send('unavailable')
        result = _future_result(handle.get_result_async())
        assert result.result.outcome == Speak.Result.OUTCOME_FAILED
        assert 'failure' in result.result.message
    finally:
        harness.close()
