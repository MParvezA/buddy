"""Publish the frozen RobotStatus summary from safety and world contracts."""

from __future__ import annotations

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from buddy_interfaces.msg import RobotStatus, SafetyState, WorldSummary

from .status_core import decide_status


STATUS_TOPIC = '/buddy/status'
SAFETY_TOPIC = '/buddy/safety/state'
WORLD_TOPIC = '/buddy/world/summary'
DIAGNOSTICS_TOPIC = '/diagnostics'


def state_qos() -> QoSProfile:
    """Return the frozen summary and state QoS."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )


class StatusSupervisor(Node):
    """Aggregate only frozen summaries; never own motion or safety policy."""

    def __init__(self) -> None:
        """Create the frozen summary subscriptions and status publisher."""
        super().__init__('status_supervisor', namespace='/buddy')
        if not self.has_parameter('use_sim_time'):
            self.declare_parameter('use_sim_time', False)
        self.declare_parameter('publish_rate_hz', 2.0)
        self._safety: SafetyState | None = None
        self._world: WorldSummary | None = None
        self._status_publisher = self.create_publisher(
            RobotStatus, STATUS_TOPIC, state_qos()
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
        self.create_subscription(
            SafetyState, SAFETY_TOPIC, self._on_safety, state_qos()
        )
        self.create_subscription(
            WorldSummary, WORLD_TOPIC, self._on_world, state_qos()
        )
        rate = float(self.get_parameter('publish_rate_hz').value)
        if rate <= 0.0:
            raise ValueError('publish_rate_hz must be positive')
        self.create_timer(1.0 / rate, self._publish)
        self._publish()

    def _on_safety(self, message: SafetyState) -> None:
        self._safety = message

    def _on_world(self, message: WorldSummary) -> None:
        self._world = message

    def _publish(self) -> None:
        decision = decide_status(self._safety, self._world)
        status = RobotStatus()
        status.header.stamp = self.get_clock().now().to_msg()
        status.header.frame_id = 'base_link'
        status.mode = decision.mode
        status.localization_state = decision.localization_state
        if self._safety is not None:
            status.safety = self._safety
        status.battery_percent = 0.0
        status.battery_state_known = False
        status.motion_ready = decision.motion_ready
        status.current_location = decision.current_location
        status.current_task = ''
        status.available_capabilities = []
        self._status_publisher.publish(status)

        diagnostics = DiagnosticArray()
        diagnostics.header.stamp = status.header.stamp
        diagnostic = DiagnosticStatus()
        diagnostic.name = 'buddy/status_supervisor'
        diagnostic.hardware_id = 'software'
        diagnostic.level = (
            DiagnosticStatus.OK
            if self._safety is not None and self._world is not None
            else DiagnosticStatus.WARN
        )
        diagnostic.message = (
            'status inputs ready'
            if diagnostic.level == DiagnosticStatus.OK
            else 'waiting for status inputs'
        )
        diagnostic.values = [
            KeyValue(
                key='safety_received',
                value=str(self._safety is not None).lower(),
            ),
            KeyValue(
                key='world_received',
                value=str(self._world is not None).lower(),
            ),
            KeyValue(
                key='motion_ready',
                value=str(status.motion_ready).lower(),
            ),
        ]
        diagnostics.status = [diagnostic]
        self._diagnostics.publish(diagnostics)


def main(args: list[str] | None = None) -> None:
    """Run the root-owned status supervisor."""
    rclpy.init(args=args)
    node = StatusSupervisor()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
