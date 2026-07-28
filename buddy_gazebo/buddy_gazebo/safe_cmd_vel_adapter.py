#!/usr/bin/env python3
"""The sole ROS-to-Gazebo motion boundary for the native Harmonic drive."""
from dataclasses import dataclass
import math
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from gz.msgs10.twist_pb2 import Twist
from gz.transport13 import Node as GzNode
import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy


def positive_finite_seconds(value: object, parameter_name: str) -> float:
    """Return a duration parameter or reject an unsafe timer configuration."""
    try:
        seconds = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{parameter_name} must be a finite positive number') from error
    if not math.isfinite(seconds) or seconds <= 0.0:
        raise ValueError(f'{parameter_name} must be a finite positive number')
    return seconds


@dataclass(frozen=True)
class AdapterHealth:
    """Steady-time state used by the controller-health heartbeat.

    The adapter may use ROS simulation time for message headers, but command
    freshness deliberately uses a monotonic clock.  A paused `/clock` must not
    make a stale command or failed Gazebo publication appear healthy.
    """

    command_freshness_ns: int
    last_command_receipt_ns: int | None = None
    last_publish_error: str | None = None

    @classmethod
    def create(cls, freshness_seconds: float) -> 'AdapterHealth':
        return cls(command_freshness_ns=int(freshness_seconds * 1_000_000_000))

    def command_received(self, now_ns: int) -> 'AdapterHealth':
        return AdapterHealth(
            command_freshness_ns=self.command_freshness_ns,
            last_command_receipt_ns=now_ns,
            last_publish_error=self.last_publish_error)

    def publish_succeeded(self) -> 'AdapterHealth':
        return AdapterHealth(
            command_freshness_ns=self.command_freshness_ns,
            last_command_receipt_ns=self.last_command_receipt_ns,
            last_publish_error=None)

    def publish_failed(self, error: Exception | str) -> 'AdapterHealth':
        return AdapterHealth(
            command_freshness_ns=self.command_freshness_ns,
            last_command_receipt_ns=self.last_command_receipt_ns,
            last_publish_error=str(error))

    def snapshot(self, now_ns: int) -> tuple[int, str, str, str, str]:
        """Return level, message, receipt state, age, and publisher state."""
        if self.last_command_receipt_ns is None:
            receipt_state = 'waiting'
            age_ms = 'unknown'
        else:
            age_ns = max(0, now_ns - self.last_command_receipt_ns)
            age_ms = f'{age_ns / 1_000_000.0:.1f}'
            receipt_state = (
                'fresh' if age_ns <= self.command_freshness_ns else 'stale')

        if self.last_publish_error is not None:
            return (
                DiagnosticStatus.ERROR,
                f'Gazebo command publication failed: {self.last_publish_error}',
                receipt_state,
                age_ms,
                'error')
        if receipt_state == 'waiting':
            return (
                DiagnosticStatus.WARN,
                'waiting for first safe command',
                receipt_state,
                age_ms,
                'ready')
        if receipt_state == 'stale':
            return (
                DiagnosticStatus.WARN,
                'safe command receipt is stale',
                receipt_state,
                age_ms,
                'ready')
        return (
            DiagnosticStatus.OK,
            'adapter and Gazebo publisher healthy',
            receipt_state,
            age_ms,
            'ready')


class SafeCommandAdapter(Node):
    """Forward frozen safe command output to Gazebo's native DiffDrive plugin."""

    def __init__(self):
        super().__init__('safe_cmd_vel_adapter')
        # rclpy declares the standard simulation-time parameter. Keep this
        # fallback for runtimes that do not, without redeclaring it on Jazzy.
        if not self.has_parameter('use_sim_time'):
            self.declare_parameter('use_sim_time', False)
        self.declare_parameter('gz_topic', '/model/buddy/watchdog/input')
        self.declare_parameter('diagnostic_period_sec', 0.1)
        self.declare_parameter('command_freshness_sec', 0.25)
        diagnostic_period_sec = positive_finite_seconds(
            self.get_parameter('diagnostic_period_sec').value,
            'diagnostic_period_sec')
        command_freshness_sec = positive_finite_seconds(
            self.get_parameter('command_freshness_sec').value,
            'command_freshness_sec')
        self._steady_time_ns = time.monotonic_ns
        self._health = AdapterHealth.create(command_freshness_sec)
        self._gz_node = GzNode()
        self._publisher = self._gz_node.advertise(
            self.get_parameter('gz_topic').value, Twist)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(
            TwistStamped, '/buddy/motion/safe_cmd_vel', self._on_command, qos)
        diagnostic_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        self._diagnostics = self.create_publisher(
            DiagnosticArray, '/diagnostics', diagnostic_qos)
        self.create_timer(diagnostic_period_sec, self._publish_diagnostics)

    def _on_command(self, command: TwistStamped) -> None:
        self._health = self._health.command_received(self._steady_time_ns())
        message = Twist()
        message.linear.x = command.twist.linear.x
        message.angular.z = command.twist.angular.z
        try:
            result = self._publisher.publish(message)
            # Gazebo Transport returns a bool in supported releases.  Keep
            # compatibility with bindings that return None for a success.
            if result is False:
                raise RuntimeError('Gazebo transport rejected command publication')
            self._health = self._health.publish_succeeded()
        except Exception as error:  # Gazebo binding errors must not kill safety diagnostics.
            self._health = self._health.publish_failed(error)
            self.get_logger().error(f'failed to publish safe command to Gazebo: {error}')

    def _publish_diagnostics(self) -> None:
        level, message, receipt_state, age_ms, publisher_state = self._health.snapshot(
            self._steady_time_ns())
        status = DiagnosticStatus()
        # This stable name is consumed by buddy_safety's controller watchdog.
        status.name = 'buddy_base_controller'
        status.hardware_id = 'gazebo'
        status.level = level
        status.message = message
        status.values = [
            KeyValue(key='adapter_process', value='running'),
            KeyValue(key='gazebo_publisher', value=publisher_state),
            KeyValue(key='safe_command_receipt', value=receipt_state),
            KeyValue(key='safe_command_receipt_age_ms', value=age_ms),
            KeyValue(
                key='command_freshness_ms',
                value=f'{self._health.command_freshness_ns / 1_000_000.0:.1f}'),
        ]
        diagnostics = DiagnosticArray()
        diagnostics.header.stamp = self.get_clock().now().to_msg()
        diagnostics.status = [status]
        self._diagnostics.publish(diagnostics)


def main() -> None:
    rclpy.init()
    node = None
    try:
        node = SafeCommandAdapter()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        try:
            if node is not None:
                node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except (KeyboardInterrupt, ExternalShutdownException):
            pass


if __name__ == '__main__':
    main()
