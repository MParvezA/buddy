from action_msgs.msg import GoalStatus, GoalStatusArray
from buddy_navigation.velocity_boundary import (
    motion_request_qos,
    NAVIGATION_REQUEST_TOPIC,
    VelocityBoundary,
)
from geometry_msgs.msg import TwistStamped
import rclpy
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
