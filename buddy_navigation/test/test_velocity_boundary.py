import time

from action_msgs.msg import GoalStatus, GoalStatusArray
from buddy_navigation.velocity_boundary import (
    motion_request_qos,
    NAVIGATION_REQUEST_TOPIC,
    VelocityBoundary,
)
from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.clock import ClockType
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, HistoryPolicy, ReliabilityPolicy


def test_motion_request_qos_is_exactly_frozen_profile():
    qos = motion_request_qos()
    assert qos.history == HistoryPolicy.KEEP_LAST
    assert qos.depth == 1
    assert qos.reliability == ReliabilityPolicy.RELIABLE
    assert qos.durability == DurabilityPolicy.VOLATILE


def test_runtime_graph_exposes_stamped_navigation_request(monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    node = VelocityBoundary()
    observer = rclpy.create_node('velocity_boundary_graph_test')
    try:
        rclpy.spin_once(observer, timeout_sec=0.1)
        endpoints = observer.get_publishers_info_by_topic(NAVIGATION_REQUEST_TOPIC)
        ours = [endpoint for endpoint in endpoints if endpoint.node_name == node.get_name()]
        assert len(ours) == 1
        endpoint = ours[0]
        assert endpoint.topic_type == 'geometry_msgs/msg/TwistStamped'
        runtime_qos = node._publisher.qos_profile
        assert runtime_qos.history == HistoryPolicy.KEEP_LAST
        assert runtime_qos.depth == 1
        assert runtime_qos.reliability == ReliabilityPolicy.RELIABLE
        assert runtime_qos.durability == DurabilityPolicy.VOLATILE
    finally:
        observer.destroy_node()
        node.destroy_node()
        rclpy.shutdown()


def test_action_cancellation_closes_velocity_gate_and_publishes_zero(
    monkeypatch, tmp_path
):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    node = VelocityBoundary()
    observer = rclpy.create_node('velocity_gate_test')
    received = []
    observer.create_subscription(
        TwistStamped,
        NAVIGATION_REQUEST_TOPIC,
        received.append,
        motion_request_qos(),
    )
    try:
        executing = GoalStatusArray()
        executing.status_list = [GoalStatus(status=GoalStatus.STATUS_EXECUTING)]
        node._on_action_status(executing)
        command = TwistStamped()
        command.twist.linear.x = 0.2
        node._forward(command)
        rclpy.spin_once(observer, timeout_sec=0.2)

        canceling = GoalStatusArray()
        canceling.status_list = [GoalStatus(status=GoalStatus.STATUS_CANCELING)]
        node._on_action_status(canceling)
        node._forward(command)
        rclpy.spin_once(observer, timeout_sec=0.2)
        rclpy.spin_once(observer, timeout_sec=0.2)

        assert len(received) == 2
        assert received[0].twist.linear.x == 0.2
        assert received[1].twist.linear.x == 0.0
        assert received[1].twist.angular.z == 0.0
    finally:
        observer.destroy_node()
        node.destroy_node()
        rclpy.shutdown()


def test_stale_action_owner_closes_gate_with_sim_time_paused(
    monkeypatch, tmp_path
):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    node = VelocityBoundary(
        parameter_overrides=[
            Parameter('use_sim_time', value=True),
            Parameter('owner_liveness_timeout_sec', value=0.1),
        ],
    )
    observer = rclpy.create_node('velocity_owner_liveness_test')
    received = []
    observer.create_subscription(
        TwistStamped,
        NAVIGATION_REQUEST_TOPIC,
        received.append,
        motion_request_qos(),
    )
    try:
        assert (
            node._owner_liveness_timer.clock.clock_type
            == ClockType.STEADY_TIME
        )
        executing = GoalStatusArray()
        executing.status_list = [
            GoalStatus(status=GoalStatus.STATUS_EXECUTING)
        ]
        node._on_action_status(executing)
        command = TwistStamped()
        command.twist.linear.x = 0.2

        started = time.monotonic()
        deadline = started + 0.5
        while time.monotonic() < deadline:
            node._forward(command)
            rclpy.spin_once(node, timeout_sec=0.005)
            rclpy.spin_once(observer, timeout_sec=0.005)
            if any(message.twist.linear.x == 0.0 for message in received):
                break

        zero_index = next(
            index
            for index, message in enumerate(received)
            if message.twist.linear.x == 0.0
        )
        zero_elapsed = time.monotonic() - started
        for _ in range(5):
            node._forward(command)
            rclpy.spin_once(node, timeout_sec=0.005)
            rclpy.spin_once(observer, timeout_sec=0.005)

        assert node.get_clock().now().nanoseconds == 0
        assert any(
            message.twist.linear.x == 0.2
            for message in received[:zero_index]
        )
        assert zero_elapsed < 0.3
        assert sum(
            message.twist.linear.x == 0.0 for message in received
        ) == 1
        assert all(
            message.twist.linear.x == 0.0
            for message in received[zero_index:]
        )
    finally:
        observer.destroy_node()
        node.destroy_node()
        rclpy.shutdown()
