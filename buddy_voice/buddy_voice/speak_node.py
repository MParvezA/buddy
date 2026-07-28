"""Frozen Speak action server backed by a replaceable local TTS provider."""

from __future__ import annotations

from threading import Condition, Event, Lock
import time

from buddy_interfaces.action import Speak
from builtin_interfaces.msg import Duration
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node

from .providers import (
    FakeTextToSpeechProvider,
    SpeechSynthesisCancelled,
    SpeechSynthesisError,
    SpeechSynthesisTimeout,
    TextToSpeechProvider,
)


SPEAK_ACTION = '/buddy/voice/speak'
VOICE_ERROR_EMPTY_TEXT = 1000
VOICE_ERROR_SYNTHESIS = 1001
VOICE_ERROR_SYNTHESIS_TIMEOUT = 1002
VOICE_ERROR_PLAYBACK_TIMEOUT = 1003


class BuddySpeakNode(Node):
    """Provides queued/synthesizing/speaking feedback for local speech output."""

    def __init__(
            self,
            text_to_speech: TextToSpeechProvider | None = None,
            *,
            playback_steps: int = 3,
            step_seconds: float = 0.02,
            synthesis_timeout_seconds: float = 5.0,
            playback_timeout_seconds: float = 30.0,
            node_name: str = 'speak_server') -> None:
        super().__init__(node_name, namespace='/buddy')
        if not self.has_parameter('use_sim_time'):
            self.declare_parameter('use_sim_time', False)
        self._text_to_speech = text_to_speech or FakeTextToSpeechProvider()
        self._playback_steps = max(1, playback_steps)
        self._step_seconds = max(0.0, step_seconds)
        self.declare_parameter('synthesis_timeout_seconds', synthesis_timeout_seconds)
        self.declare_parameter('playback_timeout_seconds', playback_timeout_seconds)
        self._synthesis_timeout_seconds = max(
            0.01, float(self.get_parameter('synthesis_timeout_seconds').value))
        self._playback_timeout_seconds = max(
            0.01, float(self.get_parameter('playback_timeout_seconds').value))
        self._action_callback_group = ReentrantCallbackGroup()
        self._cancel_events: dict[bytes, Event] = {}
        self._cancel_lock = Lock()
        self._active_condition = Condition(self._cancel_lock)
        self._active_speech = 0
        self.diagnostics_publisher = self.create_publisher(
            DiagnosticArray, '/diagnostics', 10)
        self._action_server = ActionServer(
            self,
            Speak,
            SPEAK_ACTION,
            execute_callback=self._execute,
            goal_callback=self._accept_goal,
            cancel_callback=self._accept_cancel,
            callback_group=self._action_callback_group,
        )

    @staticmethod
    def _accept_goal(goal: Speak.Goal) -> GoalResponse:
        """Reject only invalid empty speech requests before execution."""
        return GoalResponse.ACCEPT if goal.text.strip() else GoalResponse.REJECT

    def _accept_cancel(self, goal_handle: object) -> CancelResponse:
        """Every active speech request is cancellable."""
        with self._cancel_lock:
            event = self._cancel_events.get(_goal_key(goal_handle))
        if event is not None:
            event.set()
        return CancelResponse.ACCEPT

    def _execute(self, goal_handle: object) -> Speak.Result:
        """Track one active action until all provider and result work completes."""
        cancel_event = Event()
        goal_key = _goal_key(goal_handle)
        with self._active_condition:
            self._cancel_events[goal_key] = cancel_event
            self._active_speech += 1
        try:
            return self._execute_active(goal_handle, cancel_event)
        finally:
            with self._active_condition:
                self._cancel_events.pop(goal_key, None)
                self._active_speech -= 1
                self._active_condition.notify_all()

    def _execute_active(self, goal_handle: object, cancel_event: Event) -> Speak.Result:
        """Synthesize and play one request while honoring cancellation."""
        result = Speak.Result()
        self._feedback(goal_handle, Speak.Feedback.STATE_QUEUED, 0.0, 'queued')
        try:
            if goal_handle.is_cancel_requested:
                return self._cancelled_result(
                    goal_handle, result, 'speech cancelled before synthesis')
            self._feedback(goal_handle, Speak.Feedback.STATE_SYNTHESIZING, 0.0, 'synthesizing')
            speech = self._text_to_speech.synthesize(
                goal_handle.request.text,
                goal_handle.request.voice,
                cancel_event=cancel_event,
                deadline_monotonic=time.monotonic() + self._synthesis_timeout_seconds,
            )
        except SpeechSynthesisCancelled as error:
            if goal_handle.is_cancel_requested:
                return self._cancelled_result(goal_handle, result, str(error))
            return self._failed_result(
                goal_handle,
                result,
                VOICE_ERROR_SYNTHESIS,
                'speech synthesis interrupted during node shutdown',
            )
        except SpeechSynthesisTimeout as error:
            return self._failed_result(
                goal_handle, result, VOICE_ERROR_SYNTHESIS_TIMEOUT, str(error))
        except SpeechSynthesisError as error:
            return self._failed_result(goal_handle, result, VOICE_ERROR_SYNTHESIS, str(error))
        except Exception as error:  # provider boundary: unexpected provider errors are failures
            return self._failed_result(
                goal_handle,
                result,
                VOICE_ERROR_SYNTHESIS,
                f'unexpected speech provider failure: {error}',
            )
        playback_deadline = time.monotonic() + self._playback_timeout_seconds
        for step in range(self._playback_steps):
            if goal_handle.is_cancel_requested:
                return self._cancelled_result(
                    goal_handle, result, 'speech playback cancelled', speech)
            if cancel_event.is_set():
                return self._failed_result(
                    goal_handle,
                    result,
                    VOICE_ERROR_SYNTHESIS,
                    'speech playback interrupted during node shutdown',
                    speech,
                )
            if time.monotonic() >= playback_deadline:
                return self._failed_result(
                    goal_handle,
                    result,
                    VOICE_ERROR_PLAYBACK_TIMEOUT,
                    'speech playback timed out',
                    speech,
                )
            self._feedback(
                goal_handle,
                Speak.Feedback.STATE_SPEAKING,
                float(step + 1) / self._playback_steps,
                'speaking',
            )
            cancel_event.wait(min(
                self._step_seconds,
                max(0.0, playback_deadline - time.monotonic()),
            ))

        # The final wait can be interrupted after the loop's last pre-wait
        # check.  Never turn that cancellation or deadline into success.
        if goal_handle.is_cancel_requested:
            return self._cancelled_result(
                goal_handle, result, 'speech playback cancelled', speech)
        if cancel_event.is_set():
            return self._failed_result(
                goal_handle,
                result,
                VOICE_ERROR_SYNTHESIS,
                'speech playback interrupted during node shutdown',
                speech,
            )
        if time.monotonic() >= playback_deadline:
            return self._failed_result(
                goal_handle,
                result,
                VOICE_ERROR_PLAYBACK_TIMEOUT,
                'speech playback timed out',
                speech,
            )
        goal_handle.succeed()
        result.outcome = Speak.Result.OUTCOME_SUCCEEDED
        result.audio_duration = _duration_message(speech.duration_seconds)
        result.message = 'speech playback completed'
        return result

    def _cancelled_result(
            self,
            goal_handle: object,
            result: Speak.Result,
            message: str,
            speech: object | None = None) -> Speak.Result:
        """Return the frozen cancelled result and action transport state."""
        goal_handle.canceled()
        result.outcome = Speak.Result.OUTCOME_CANCELLED
        result.audio_duration = _duration_message(
            getattr(speech, 'duration_seconds', 0.0))
        result.message = message or 'speech cancelled'
        return result

    def _failed_result(
            self,
            goal_handle: object,
            result: Speak.Result,
            error_code: int,
            message: str,
            speech: object | None = None) -> Speak.Result:
        """Abort a failed provider/playback call with a diagnostic event."""
        detail = message or 'speech output failed without a provider message'
        self._publish_failure_diagnostic(error_code, detail)
        goal_handle.abort()
        result.outcome = Speak.Result.OUTCOME_FAILED
        result.audio_duration = _duration_message(
            getattr(speech, 'duration_seconds', 0.0))
        result.message = detail
        return result

    def _publish_failure_diagnostic(self, error_code: int, message: str) -> None:
        """Report every structured output failure on the frozen diagnostics topic."""
        self.get_logger().error(message)
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.level = DiagnosticStatus.ERROR
        status.name = 'buddy_voice/speak_server'
        status.message = message
        status.hardware_id = 'local_tts'
        status.values = [KeyValue(key='error_code', value=str(error_code))]
        array.status = [status]
        self.diagnostics_publisher.publish(array)

    def cancel_active_speech(self) -> None:
        """Signal all cooperative provider calls before executor shutdown."""
        with self._cancel_lock:
            for cancel_event in self._cancel_events.values():
                cancel_event.set()

    def wait_for_active_speech(self, timeout_seconds: float = 1.0) -> bool:
        """Drain cooperative work and its action result before ROS destruction."""
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        with self._active_condition:
            while self._active_speech or self._has_pending_action_result():
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    return False
                # ActionServer completes its result future immediately after our
                # callback returns, outside this condition.  Poll briefly while
                # the executor is still spinning instead of destroying its handle.
                self._active_condition.wait(min(0.01, remaining))
            return True

    def _has_pending_action_result(self) -> bool:
        """Check ActionServer's in-process result futures during orderly drain."""
        return any(
            not future.done()
            for future in self._action_server._result_futures.values()
        )

    @staticmethod
    def _feedback(goal_handle: object, state: int, progress: float, message: str) -> None:
        feedback = Speak.Feedback()
        feedback.state = state
        feedback.progress = progress
        feedback.message = message
        goal_handle.publish_feedback(feedback)

    def destroy_node(self) -> bool:
        """Destroy the action server before the underlying ROS node."""
        self.cancel_active_speech()
        self.wait_for_active_speech()
        self._action_server.destroy()
        return super().destroy_node()


def _duration_message(seconds: float) -> Duration:
    """Encode non-negative duration seconds in the frozen action result field."""
    value = max(0.0, seconds)
    message = Duration()
    message.sec = int(value)
    message.nanosec = int((value - message.sec) * 1_000_000_000)
    return message


def _goal_key(goal_handle: object) -> bytes:
    """Return a stable key for a server goal handle's frozen UUID."""
    return bytes(goal_handle.goal_id.uuid)


def create_speak_executor() -> MultiThreadedExecutor:
    """Create the production executor that keeps cancel callbacks responsive."""
    return MultiThreadedExecutor(num_threads=2)


def main(args: list[str] | None = None) -> None:
    """Run the local mock-backed Speak action server."""
    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = BuddySpeakNode()
        executor = create_speak_executor()
        executor.add_node(node)
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.cancel_active_speech()
            node.wait_for_active_speech()
        if executor is not None:
            executor.shutdown()
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
