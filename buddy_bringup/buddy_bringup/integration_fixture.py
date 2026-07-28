"""Frozen-interface fakes used only by root-owned integration tests."""

from __future__ import annotations

import time

import rclpy
from geometry_msgs.msg import TwistStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from buddy_interfaces.action import Speak


PRIVATE_NAV2_TOPIC = '/buddy/navigation/cmd_vel_smoothed'
SPOKEN_OBSERVATION_TOPIC = (
    '/buddy/test/spoken'
)


class IntegrationFixture(Node):
    """Provide deterministic Nav2 and speech neighbors through ROS contracts."""

    def __init__(self) -> None:
        """Create action fakes and test-only observations."""
        super().__init__('integration_fixture')
        self.declare_parameter('movement_seconds', 0.6)
        self._group = ReentrantCallbackGroup()
        self._velocity = self.create_publisher(
            TwistStamped, PRIVATE_NAV2_TOPIC, 10
        )
        self._spoken = self.create_publisher(
            String, SPOKEN_OBSERVATION_TOPIC, 10
        )
        self._nav_server = ActionServer(
            self,
            NavigateToPose,
            '/navigate_to_pose',
            execute_callback=self._navigate,
            goal_callback=self._accept,
            cancel_callback=self._cancel,
            callback_group=self._group,
        )
        self._speak_server = ActionServer(
            self,
            Speak,
            '/buddy/voice/speak',
            execute_callback=self._speak,
            goal_callback=self._accept,
            cancel_callback=self._cancel,
            callback_group=self._group,
        )

    @staticmethod
    def _accept(_request) -> GoalResponse:
        return GoalResponse.ACCEPT

    @staticmethod
    def _cancel(_goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    def _navigate(self, goal_handle) -> NavigateToPose.Result:
        feedback = NavigateToPose.Feedback()
        feedback.current_pose = goal_handle.request.pose
        feedback.distance_remaining = 0.5
        started = time.monotonic()
        duration = float(self.get_parameter('movement_seconds').value)
        while time.monotonic() - started < duration:
            if goal_handle.is_cancel_requested:
                self._publish_velocity(0.0)
                goal_handle.canceled()
                return NavigateToPose.Result()
            self._publish_velocity(0.18)
            goal_handle.publish_feedback(feedback)
            time.sleep(0.03)
        self._publish_velocity(0.0)
        goal_handle.succeed()
        return NavigateToPose.Result()

    def _speak(self, goal_handle) -> Speak.Result:
        observation = String()
        observation.data = goal_handle.request.text
        self._spoken.publish(observation)
        result = Speak.Result()
        if goal_handle.is_cancel_requested:
            result.outcome = Speak.Result.OUTCOME_CANCELLED
            result.message = 'integration speech cancelled'
            goal_handle.canceled()
            return result
        result.outcome = Speak.Result.OUTCOME_SUCCEEDED
        result.message = 'integration speech completed'
        goal_handle.succeed()
        return result

    def _publish_velocity(self, linear_x: float) -> None:
        command = TwistStamped()
        command.header.stamp = self.get_clock().now().to_msg()
        command.header.frame_id = 'base_link'
        command.twist.linear.x = linear_x
        self._velocity.publish(command)

    def destroy_node(self) -> bool:
        """Destroy action servers before their node and waitables."""
        self._nav_server.destroy()
        self._speak_server.destroy()
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    """Run deterministic frozen-interface integration fakes."""
    rclpy.init(args=args)
    node = IntegrationFixture()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
