"""Publish Nav2's private stamped velocity with the frozen motion-request QoS."""

import math

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
OWNER_LIVENESS_TIMEOUT_SEC = 0.2
MAX_LIVENESS_CHECK_PERIOD_SEC = 0.05
STARTUP_DIAGNOSTIC_DELAY_SEC = 0.01
DIAGNOSTIC_NAME = 'buddy/navigation/velocity_boundary'


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
        if (
            not math.isfinite(self._owner_liveness_timeout_sec)
            or self._owner_liveness_timeout_sec <= 0.0
        ):
            raise ValueError(
                'owner_liveness_timeout_sec must be finite and positive'
            )
        self._action_executing = False
        self._last_owner_evidence_ns = None
        self._diagnostic_state = None
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
        self._startup_diagnostic_timer = self.create_timer(
            STARTUP_DIAGNOSTIC_DELAY_SEC,
            self._publish_startup_diagnostic,
            clock=self._owner_liveness_clock,
        )

    def _forward(self, message: TwistStamped) -> None:
        if not self._action_executing:
            return
        if message.header.stamp.sec == 0 and message.header.stamp.nanosec == 0:
            message.header.stamp = self.get_clock().now().to_msg()
        self._publisher.publish(message)
        self._count += 1
        self._publish_diagnostic(
            state='forwarding',
            level=DiagnosticStatus.OK,
            message='forwarding stamped Nav2 motion requests',
            reason='owned_action_and_nav2_command_live',
        )

    def _on_action_status(self, status_array: GoalStatusArray) -> None:
        executing = any(
            status.status == GoalStatus.STATUS_EXECUTING
            for status in status_array.status_list
        )
        if executing:
            self._last_owner_evidence_ns = (
                self._owner_liveness_clock.now().nanoseconds
            )
            was_executing = self._action_executing
            self._action_executing = True
            if not was_executing:
                self._publish_diagnostic(
                    state='owner_live',
                    level=DiagnosticStatus.OK,
                    message='navigation action owner live; velocity gate active',
                    reason='executing_action_status',
                )
        elif self._action_executing:
            self._close_gate(
                reason='action_no_longer_executing',
                level=DiagnosticStatus.OK,
                message='velocity gate closed after normal action transition',
                elapsed_sec=self._owner_evidence_elapsed_sec(),
            )

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
            self._close_gate(
                reason='owner_liveness_timeout',
                level=DiagnosticStatus.ERROR,
                message='velocity gate closed: navigation action owner timed out',
                elapsed_sec=elapsed_sec,
            )

    def _close_gate(
        self,
        *,
        reason: str,
        level: int,
        message: str,
        elapsed_sec: float | None,
    ) -> None:
        self._action_executing = False
        self._last_owner_evidence_ns = None
        stopped = TwistStamped()
        stopped.header.stamp = self.get_clock().now().to_msg()
        stopped.header.frame_id = 'base_link'
        self._publisher.publish(stopped)
        self._publish_diagnostic(
            state='gate_inactive',
            level=level,
            message=message,
            reason=reason,
            elapsed_sec=elapsed_sec,
        )

    def _owner_evidence_elapsed_sec(self) -> float | None:
        if self._last_owner_evidence_ns is None:
            return None
        return (
            self._owner_liveness_clock.now().nanoseconds
            - self._last_owner_evidence_ns
        ) / 1e9

    def _publish_startup_diagnostic(self) -> None:
        self._startup_diagnostic_timer.cancel()
        if self._diagnostic_state is not None:
            return
        self._publish_diagnostic(
            state='gate_inactive',
            level=DiagnosticStatus.WARN,
            message='velocity gate inactive; awaiting navigation action owner',
            reason='startup_awaiting_action',
        )

    def _publish_diagnostic(
        self,
        *,
        state: str,
        level: int,
        message: str,
        reason: str,
        elapsed_sec: float | None = None,
    ) -> None:
        diagnostic_state = (state, level, reason)
        if diagnostic_state == self._diagnostic_state:
            return
        self._diagnostic_state = diagnostic_state
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = DIAGNOSTIC_NAME
        status.hardware_id = 'software'
        status.level = level
        status.message = message
        status.values = [
            KeyValue(key='state', value=state),
            KeyValue(
                key='gate_active',
                value=str(self._action_executing).lower(),
            ),
            KeyValue(key='reason', value=reason),
            KeyValue(
                key='owner_elapsed_sec',
                value=(
                    f'{elapsed_sec:.6f}'
                    if elapsed_sec is not None
                    else 'not_available'
                ),
            ),
            KeyValue(
                key='owner_lease_sec',
                value=f'{self._owner_liveness_timeout_sec:.6f}',
            ),
            KeyValue(key='liveness_clock', value='steady_time'),
            KeyValue(key='forwarded_count', value=str(self._count)),
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
