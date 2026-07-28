"""ROS action tests for bounded Speak synthesis, playback, and cancellation."""

from concurrent.futures import ThreadPoolExecutor
import time

from action_msgs.msg import GoalStatus
from buddy_interfaces.action import Speak
from buddy_voice.providers import FakeTextToSpeechProvider
from buddy_voice.speak_node import BuddySpeakNode, create_speak_executor, SPEAK_ACTION
from diagnostic_msgs.msg import DiagnosticArray
import rclpy
from rclpy.action import ActionClient


def _future_result(future: object, timeout: float = 2.0) -> object:
    """Wait for an rclpy future, whose result method has no timeout argument."""
    deadline = time.monotonic() + timeout
    while not future.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert future.done(), 'ROS future did not complete before its test timeout'
    return future.result()


def _wait_until(predicate: object, timeout: float = 1.0) -> None:
    """Wait for a callback-driven predicate without depending on ROS time."""
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert predicate(), 'expected callback did not arrive before its test timeout'


class SpeakHarness:
    """Own an isolated action pair using BuddySpeakNode's production executor."""

    def __init__(
            self,
            provider: FakeTextToSpeechProvider,
            *,
            steps: int = 3,
            delay: float = 0.01,
            synthesis_timeout: float = 5.0,
            playback_timeout: float = 30.0) -> None:
        rclpy.init()
        self.server = BuddySpeakNode(
            provider,
            playback_steps=steps,
            step_seconds=delay,
            synthesis_timeout_seconds=synthesis_timeout,
            playback_timeout_seconds=playback_timeout,
        )
        self.client_node = rclpy.create_node('speak_component_client')
        self.client = ActionClient(self.client_node, Speak, SPEAK_ACTION)
        self.diagnostics: list[DiagnosticArray] = []
        self.diagnostic_subscription = self.client_node.create_subscription(
            DiagnosticArray,
            '/diagnostics',
            self.diagnostics.append,
            10,
        )
        # This is deliberately the exact two-thread executor selected by main(),
        # rather than a test-only executor that could hide cancel starvation.
        self.executor = create_speak_executor()
        self.executor.add_node(self.server)
        self.executor.add_node(self.client_node)
        self.thread = ThreadPoolExecutor(max_workers=1)
        self.thread.submit(self.executor.spin)
        assert self.client.wait_for_server(timeout_sec=2.0)

    def close(self) -> None:
        """Stop the production-configured executor and all ROS resources."""
        self.server.cancel_active_speech()
        assert self.server.wait_for_active_speech()
        # The client can still have a queued callback after its final result;
        # draining it is required, but its cancellation is a normal teardown
        # outcome rather than a test failure.
        self.executor.drain_submitted_callbacks(0.25)
        assert self.executor.shutdown_workers(0.25)
        self.executor.remove_node(self.server)
        self.executor.remove_node(self.client_node)
        self.executor.shutdown(timeout_sec=0.0)
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
    """Normal local speech returns frozen success and expected feedback states."""
    harness = SpeakHarness(FakeTextToSpeechProvider(duration_seconds=0.25))
    feedback: list[Speak.Feedback] = []
    try:
        handle = harness.send('hello', feedback)
        result = _future_result(handle.get_result_async())
        assert result.status == GoalStatus.STATUS_SUCCEEDED
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


def test_production_executor_cancels_long_playback_promptly() -> None:
    """A one-second playback wait is interrupted by the production executor."""
    harness = SpeakHarness(FakeTextToSpeechProvider(), steps=2, delay=1.0)
    try:
        handle = harness.send('long playback')
        time.sleep(0.05)
        cancel_started = time.monotonic()
        cancel_response = _future_result(handle.cancel_goal_async())
        result = _future_result(handle.get_result_async())
        assert cancel_response.goals_canceling
        assert time.monotonic() - cancel_started < 0.4
        assert result.status == GoalStatus.STATUS_CANCELED
        assert result.result.outcome == Speak.Result.OUTCOME_CANCELLED
    finally:
        harness.close()


def test_cancel_during_the_only_playback_wait_is_not_reported_as_success() -> None:
    """The final playback wait rechecks cancellation before completing the goal."""
    harness = SpeakHarness(FakeTextToSpeechProvider(), steps=1, delay=1.0)
    try:
        handle = harness.send('single long playback step')
        time.sleep(0.05)
        assert _future_result(handle.cancel_goal_async()).goals_canceling
        result = _future_result(handle.get_result_async())
        assert result.status == GoalStatus.STATUS_CANCELED
        assert result.result.outcome == Speak.Result.OUTCOME_CANCELLED
    finally:
        harness.close()


def test_synthesis_cancellation_is_prompt_and_has_no_playback_worker() -> None:
    """Cooperative synthesis observes cancel before a long fake provider delay."""
    provider = FakeTextToSpeechProvider(synthesis_delay_seconds=1.0)
    harness = SpeakHarness(provider)
    try:
        handle = harness.send('slow synthesis')
        time.sleep(0.05)
        cancel_started = time.monotonic()
        assert _future_result(handle.cancel_goal_async()).goals_canceling
        result = _future_result(handle.get_result_async())
        assert time.monotonic() - cancel_started < 0.4
        assert result.status == GoalStatus.STATUS_CANCELED
        assert result.result.outcome == Speak.Result.OUTCOME_CANCELLED
        assert 'cancel' in result.result.message
    finally:
        harness.close()


def test_synthesis_timeout_aborts_with_structured_failure_and_diagnostic() -> None:
    """Steady-clock synthesis deadline works independently of simulation time."""
    provider = FakeTextToSpeechProvider(synthesis_delay_seconds=0.5)
    harness = SpeakHarness(provider, synthesis_timeout=0.05)
    try:
        handle = harness.send('slow synthesis')
        result = _future_result(handle.get_result_async())
        _wait_until(lambda: bool(harness.diagnostics))
        assert result.status == GoalStatus.STATUS_ABORTED
        assert result.result.outcome == Speak.Result.OUTCOME_FAILED
        assert 'timed out' in result.result.message
        assert harness.diagnostics[-1].status[0].values[0].value == '1002'
    finally:
        harness.close()


def test_unexpected_provider_error_is_structured_action_failure() -> None:
    """Unexpected provider exceptions never become default-success results."""
    harness = SpeakHarness(FakeTextToSpeechProvider(unexpected_for={'unexpected'}))
    try:
        handle = harness.send('unexpected')
        result = _future_result(handle.get_result_async())
        _wait_until(lambda: bool(harness.diagnostics))
        assert result.status == GoalStatus.STATUS_ABORTED
        assert result.result.outcome == Speak.Result.OUTCOME_FAILED
        assert result.result.message
        assert 'unexpected speech provider failure' in result.result.message
    finally:
        harness.close()


def test_playback_timeout_aborts_instead_of_running_indefinitely() -> None:
    """Playback has an independent steady-clock liveness bound."""
    harness = SpeakHarness(
        FakeTextToSpeechProvider(),
        steps=10,
        delay=0.05,
        playback_timeout=0.07,
    )
    try:
        handle = harness.send('long playback')
        result = _future_result(handle.get_result_async())
        assert result.status == GoalStatus.STATUS_ABORTED
        assert result.result.outcome == Speak.Result.OUTCOME_FAILED
        assert 'timed out' in result.result.message
    finally:
        harness.close()


def test_timeout_during_the_only_playback_wait_is_not_reported_as_success() -> None:
    """The final playback wait rechecks its steady-clock timeout before success."""
    harness = SpeakHarness(
        FakeTextToSpeechProvider(),
        steps=1,
        delay=0.1,
        playback_timeout=0.05,
    )
    try:
        handle = harness.send('single timed playback step')
        result = _future_result(handle.get_result_async())
        assert result.status == GoalStatus.STATUS_ABORTED
        assert result.result.outcome == Speak.Result.OUTCOME_FAILED
        assert 'timed out' in result.result.message
    finally:
        harness.close()


def test_active_cooperative_synthesis_does_not_block_clean_teardown() -> None:
    """Shutdown signals a provider boundary instead of retaining a worker thread."""
    harness = SpeakHarness(FakeTextToSpeechProvider(synthesis_delay_seconds=5.0))
    try:
        handle = harness.send('slow synthesis')
        result_future = handle.get_result_async()
        time.sleep(0.05)
        harness.server.cancel_active_speech()
        result = _future_result(result_future)
        assert result.status == GoalStatus.STATUS_ABORTED
        close_started = time.monotonic()
        harness.close()
        assert time.monotonic() - close_started < 0.4
    finally:
        if rclpy.ok():
            harness.close()
