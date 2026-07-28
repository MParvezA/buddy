"""Publish Nav2's private stamped velocity with the frozen motion-request QoS."""

from action_msgs.msg import GoalStatus, GoalStatusArray
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy


PRIVATE_NAV2_TOPIC = '/buddy/navigation/cmd_vel_smoothed'
NAVIGATION_REQUEST_TOPIC = '/buddy/motion/request/navigation'
ACTION_STATUS_TOPIC = (
    '/buddy/navigation/navigate_to_named_location/_action/status'
)
DIAGNOSTICS_TOPIC = '/diagnostics'
OWNER_LIVENESS_TIMEOUT_SEC = 0.5
MAX_LIVENESS_CHECK_PERIOD_SEC = 0.05


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

    def __init__(self, *, parameter_overrides=None) -> None:
        super().__init__(
            'navigation_velocity_boundary',
            namespace='/buddy',
            parameter_overrides=parameter_overrides,
        )
        self.declare_parameter(
            'owner_liveness_timeout_sec',
            OWNER_LIVENESS_TIMEOUT_SEC,
        )
        self._owner_liveness_timeout_sec = float(
            self.get_parameter('owner_liveness_timeout_sec').value
        )
        if self._owner_liveness_timeout_sec <= 0.0:
            raise ValueError('owner_liveness_timeout_sec must be positive')
        self._action_executing = False
        self._last_owner_evidence_ns = None
        self._owner_liveness_clock = Clock(clock_type=ClockType.STEADY_TIME)
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
        check_period = min(
            MAX_LIVENESS_CHECK_PERIOD_SEC,
            self._owner_liveness_timeout_sec / 4.0,
        )
        self._owner_liveness_timer = self.create_timer(
            check_period,
            self._check_owner_liveness,
            clock=self._owner_liveness_clock,
        )

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
        executing = any(
            status.status == GoalStatus.STATUS_EXECUTING
            for status in status_array.status_list
        )
        if executing:
            self._last_owner_evidence_ns = (
                self._owner_liveness_clock.now().nanoseconds
            )
            self._action_executing = True
        elif self._action_executing:
            self._close_gate()

    def _check_owner_liveness(self) -> None:
        if (
            not self._action_executing
            or self._last_owner_evidence_ns is None
        ):
            return
        elapsed_sec = (
            self._owner_liveness_clock.now().nanoseconds
            - self._last_owner_evidence_ns
        ) / 1e9
        if elapsed_sec >= self._owner_liveness_timeout_sec:
            self._close_gate()

    def _close_gate(self) -> None:
        self._action_executing = False
        self._last_owner_evidence_ns = None
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
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        try:
            node.destroy_node()
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
        if rclpy.ok():
            try:
                rclpy.shutdown()
            except (KeyboardInterrupt, ExternalShutdownException):
                pass
