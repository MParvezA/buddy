"""Frozen Speak action server backed by a replaceable local TTS provider."""

from __future__ import annotations

import time

from buddy_interfaces.action import Speak
from builtin_interfaces.msg import Duration
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from .providers import FakeTextToSpeechProvider, SpeechSynthesisError, TextToSpeechProvider


SPEAK_ACTION = '/buddy/voice/speak'
VOICE_ERROR_EMPTY_TEXT = 1000
VOICE_ERROR_SYNTHESIS = 1001


class BuddySpeakNode(Node):
    """Provides queued/synthesizing/speaking feedback for local speech output."""

    def __init__(
            self,
            text_to_speech: TextToSpeechProvider | None = None,
            *,
            playback_steps: int = 3,
            step_seconds: float = 0.02,
            node_name: str = 'speak_server') -> None:
        super().__init__(node_name, namespace='/buddy')
        if not self.has_parameter('use_sim_time'):
            self.declare_parameter('use_sim_time', False)
        self._text_to_speech = text_to_speech or FakeTextToSpeechProvider()
        self._playback_steps = max(1, playback_steps)
        self._step_seconds = max(0.0, step_seconds)
        self._action_server = ActionServer(
            self,
            Speak,
            SPEAK_ACTION,
            execute_callback=self._execute,
            goal_callback=self._accept_goal,
            cancel_callback=self._accept_cancel,
        )

    @staticmethod
    def _accept_goal(goal: Speak.Goal) -> GoalResponse:
        """Reject only invalid empty speech requests before execution."""
        return GoalResponse.ACCEPT if goal.text.strip() else GoalResponse.REJECT

    @staticmethod
    def _accept_cancel(_: object) -> CancelResponse:
        """Every active speech request is cancellable."""
        return CancelResponse.ACCEPT

    def _execute(self, goal_handle: object) -> Speak.Result:
        """Synthesize and play one request while honoring cancellation."""
        result = Speak.Result()
        self._feedback(goal_handle, Speak.Feedback.STATE_QUEUED, 0.0, 'queued')
        try:
            speech = self._text_to_speech.synthesize(
                goal_handle.request.text, goal_handle.request.voice)
        except SpeechSynthesisError as error:
            goal_handle.abort()
            result.outcome = Speak.Result.OUTCOME_FAILED
            result.audio_duration = Duration()
            result.message = str(error)
            return result

        self._feedback(goal_handle, Speak.Feedback.STATE_SYNTHESIZING, 0.0, 'synthesized')
        for step in range(self._playback_steps):
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.outcome = Speak.Result.OUTCOME_CANCELLED
                result.audio_duration = _duration_message(speech.duration_seconds)
                result.message = 'speech playback cancelled'
                return result
            self._feedback(
                goal_handle,
                Speak.Feedback.STATE_SPEAKING,
                float(step + 1) / self._playback_steps,
                'speaking',
            )
            time.sleep(self._step_seconds)

        goal_handle.succeed()
        result.outcome = Speak.Result.OUTCOME_SUCCEEDED
        result.audio_duration = _duration_message(speech.duration_seconds)
        result.message = 'speech playback completed'
        return result

    @staticmethod
    def _feedback(goal_handle: object, state: int, progress: float, message: str) -> None:
        feedback = Speak.Feedback()
        feedback.state = state
        feedback.progress = progress
        feedback.message = message
        goal_handle.publish_feedback(feedback)

    def destroy_node(self) -> bool:
        """Destroy the action server before the underlying ROS node."""
        self._action_server.destroy()
        return super().destroy_node()


def _duration_message(seconds: float) -> Duration:
    """Encode non-negative duration seconds in the frozen action result field."""
    value = max(0.0, seconds)
    message = Duration()
    message.sec = int(value)
    message.nanosec = int((value - message.sec) * 1_000_000_000)
    return message


def main(args: list[str] | None = None) -> None:
    """Run the local mock-backed Speak action server."""
    rclpy.init(args=args)
    node = None
    try:
        node = BuddySpeakNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
