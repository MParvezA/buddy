"""Publish Nav2's private stamped velocity with the frozen motion-request QoS."""

from action_msgs.msg import GoalStatus, GoalStatusArray
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy


PRIVATE_NAV2_TOPIC = '/buddy/navigation/cmd_vel_smoothed'
NAVIGATION_REQUEST_TOPIC = '/buddy/motion/request/navigation'
ACTION_STATUS_TOPIC = (
    '/buddy/navigation/navigate_to_named_location/_action/status'
)
DIAGNOSTICS_TOPIC = '/diagnostics'


def motion_request_qos() -> QoSProfile:
    """Return the exact frozen motion-request QoS."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )


class VelocityBoundary(Node):
    """A type/QoS boundary only; motion policy remains in safety and arbitration."""

    def __init__(self) -> None:
        super().__init__('navigation_velocity_boundary', namespace='/buddy')
        self._publisher = self.create_publisher(
            TwistStamped, NAVIGATION_REQUEST_TOPIC, motion_request_qos()
        )
        input_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(
            TwistStamped, PRIVATE_NAV2_TOPIC, self._forward, input_qos
        )
        action_status_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            GoalStatusArray,
            ACTION_STATUS_TOPIC,
            self._on_action_status,
            action_status_qos,
        )
        diagnostics_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._diagnostics = self.create_publisher(
            DiagnosticArray, DIAGNOSTICS_TOPIC, diagnostics_qos
        )
        self._count = 0
        self._action_executing = False

    def _forward(self, message: TwistStamped) -> None:
        if not self._action_executing:
            return
        if message.header.stamp.sec == 0 and message.header.stamp.nanosec == 0:
            message.header.stamp = self.get_clock().now().to_msg()
        self._publisher.publish(message)
        self._count += 1
        if self._count == 1:
            self._publish_ready()

    def _on_action_status(self, status_array: GoalStatusArray) -> None:
        was_executing = self._action_executing
        self._action_executing = any(
            status.status == GoalStatus.STATUS_EXECUTING
            for status in status_array.status_list
        )
        if was_executing and not self._action_executing:
            stopped = TwistStamped()
            stopped.header.stamp = self.get_clock().now().to_msg()
            stopped.header.frame_id = 'base_link'
            self._publisher.publish(stopped)

    def _publish_ready(self) -> None:
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = 'buddy/navigation/velocity_boundary'
        status.hardware_id = 'software'
        status.level = DiagnosticStatus.OK
        status.message = 'forwarding stamped Nav2 motion requests'
        status.values = [
            KeyValue(key='output_topic', value=NAVIGATION_REQUEST_TOPIC),
            KeyValue(key='message_type', value='geometry_msgs/msg/TwistStamped'),
            KeyValue(key='qos', value='reliable/volatile/keep_last:1'),
        ]
        array.status = [status]
        self._diagnostics.publish(array)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VelocityBoundary()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
