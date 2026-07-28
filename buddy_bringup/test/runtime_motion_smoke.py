#!/usr/bin/env python3
"""Probe a running production launch through frozen motion and safety contracts."""

from __future__ import annotations

import time

from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from buddy_interfaces.msg import EmergencyStopRequest, SafetyState
from buddy_interfaces.srv import ResetEmergencyStop


class MotionProbe(Node):
    """Publish only registered movement sources and observe filtered output."""

    def __init__(self) -> None:
        super().__init__(
            'buddy_runtime_motion_probe',
            parameter_overrides=[Parameter('use_sim_time', value=True)],
        )
        motion_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        event_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        state_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        sensor_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.navigation = self.create_publisher(
            TwistStamped, '/buddy/motion/request/navigation', motion_qos
        )
        self.teleop = self.create_publisher(
            TwistStamped, '/buddy/motion/request/teleop', motion_qos
        )
        self.emergency = self.create_publisher(
            EmergencyStopRequest,
            '/buddy/safety/emergency_stop/request',
            event_qos,
        )
        self.reset = self.create_client(
            ResetEmergencyStop, '/buddy/safety/emergency_stop/reset'
        )
        self.safe_values: list[float] = []
        self.safety: SafetyState | None = None
        self.odom_x: float | None = None
        self.create_subscription(
            TwistStamped,
            '/buddy/motion/safe_cmd_vel',
            lambda message: self.safe_values.append(message.twist.linear.x),
            motion_qos,
        )
        self.create_subscription(
            SafetyState,
            '/buddy/safety/state',
            self._on_safety,
            state_qos,
        )
        self.create_subscription(
            Odometry,
            '/odom/wheel',
            self._on_odometry,
            sensor_qos,
        )

    def _on_safety(self, message: SafetyState) -> None:
        self.safety = message

    def _on_odometry(self, message: Odometry) -> None:
        self.odom_x = message.pose.pose.position.x

    def command(self, linear_x: float) -> TwistStamped:
        """Create a correctly stamped planar movement request."""
        message = TwistStamped()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'base_link'
        message.twist.linear.x = linear_x
        return message

    def publish_emergency_stop(self) -> None:
        """Latch emergency stop through the frozen event interface."""
        request = EmergencyStopRequest()
        request.header.stamp = self.get_clock().now().to_msg()
        request.source = 'integration_validation'
        request.reason_code = EmergencyStopRequest.REASON_OPERATOR
        request.reason = 'runtime safety validation'
        self.emergency.publish(request)


def spin_until(node: Node, predicate, timeout: float = 8.0) -> None:
    """Spin until a condition is true or fail with a bounded timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        if predicate():
            return
    raise AssertionError('timed out waiting for runtime motion state')


def publish_for(
    node: MotionProbe,
    duration: float,
    *,
    navigation: float | None = None,
    teleop: float | None = None,
) -> None:
    """Publish fresh commands while spinning subscriptions."""
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        if navigation is not None:
            node.navigation.publish(node.command(navigation))
        if teleop is not None:
            node.teleop.publish(node.command(teleop))
        rclpy.spin_once(node, timeout_sec=0.05)


def main() -> None:
    """Validate priority, stale stop, emergency latch, and explicit reset."""
    rclpy.init()
    node = MotionProbe()
    try:
        spin_until(
            node,
            lambda: node.get_clock().now().nanoseconds > 0
            and node.safety is not None
            and node.safety.motion_permitted
            and node.odom_x is not None,
        )

        initial_odom_x = node.odom_x
        start = len(node.safe_values)
        publish_for(node, 1.0, navigation=0.06, teleop=0.18)
        selected = node.safe_values[start:]
        assert selected and max(selected) > 0.14, selected

        fallback_start = len(node.safe_values)
        publish_for(node, 0.6, navigation=0.06)
        fallback = node.safe_values[fallback_start:]
        assert any(0.03 < value < 0.09 for value in fallback), fallback
        assert node.odom_x is not None and initial_odom_x is not None
        assert node.odom_x - initial_odom_x > 0.05, (
            initial_odom_x,
            node.odom_x,
        )

        spin_until(
            node,
            lambda: node.safe_values and abs(node.safe_values[-1]) < 1.0e-9,
            timeout=1.0,
        )

        node.publish_emergency_stop()
        spin_until(
            node,
            lambda: node.safety is not None
            and node.safety.emergency_stop_latched
            and not node.safety.motion_permitted
            and node.safe_values
            and abs(node.safe_values[-1]) < 1.0e-9,
        )

        assert node.reset.wait_for_service(timeout_sec=3.0)
        reset = ResetEmergencyStop.Request()
        reset.source = 'operator'
        reset.reason = 'runtime validation complete'
        reset.operator_acknowledged = True
        future = node.reset.call_async(reset)
        spin_until(node, future.done)
        response = future.result()
        assert response is not None and response.success, response
        spin_until(
            node,
            lambda: node.safety is not None
            and not node.safety.emergency_stop_latched
            and node.safety.motion_permitted,
        )
        print(
            'Buddy runtime motion passed: teleop priority, navigation '
            'fallback, controller odometry, stale stop, emergency latch, '
            'and explicit reset'
        )
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
