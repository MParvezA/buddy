"""Publish the frozen RobotStatus summary from safety and world contracts."""

from __future__ import annotations

import math
import time

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.clock import Clock, ClockType
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
        self.declare_parameter('input_freshness_timeout_sec', 2.5)
        self._safety: SafetyState | None = None
        self._world: WorldSummary | None = None
        self._safety_received_steady: float | None = None
        self._world_received_steady: float | None = None
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
        freshness_timeout = float(
            self.get_parameter('input_freshness_timeout_sec').value
        )
        if not math.isfinite(freshness_timeout) or freshness_timeout <= 0.0:
            raise ValueError(
                'input_freshness_timeout_sec must be finite and positive'
            )
        # Readiness liveness must continue to expire while simulation time is
        # paused, so both receipt age and the supervisor timer use steady time.
        self._steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(
            1.0 / rate, self._publish, clock=self._steady_clock
        )
        self._publish()

    def _on_safety(self, message: SafetyState) -> None:
        self._safety = message
        self._safety_received_steady = time.monotonic()

    def _on_world(self, message: WorldSummary) -> None:
        self._world = message
        self._world_received_steady = time.monotonic()

    def _publish(self) -> None:
        now_steady = time.monotonic()
        timeout = float(
            self.get_parameter('input_freshness_timeout_sec').value
        )
        safety_fresh = self._is_fresh(
            self._safety, self._safety_received_steady, now_steady, timeout
        )
        world_fresh = self._is_fresh(
            self._world, self._world_received_steady, now_steady, timeout
        )
        safety = self._safety if safety_fresh else None
        world = self._world if world_fresh else None
        decision = decide_status(safety, world)
        status = RobotStatus()
        status.header.stamp = self.get_clock().now().to_msg()
        status.header.frame_id = 'base_link'
        status.mode = decision.mode
        status.localization_state = decision.localization_state
        if safety is not None:
            status.safety = safety
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
        any_stale = (
            (self._safety is not None and not safety_fresh)
            or (self._world is not None and not world_fresh)
        )
        if safety_fresh and world_fresh:
            diagnostic.level = DiagnosticStatus.OK
            diagnostic.message = 'status inputs ready'
        elif any_stale:
            diagnostic.level = DiagnosticStatus.ERROR
            diagnostic.message = 'status input heartbeat is stale'
        else:
            diagnostic.level = DiagnosticStatus.WARN
            diagnostic.message = 'waiting for status inputs'
        diagnostic.values = [
            KeyValue(
                key='safety_received',
                value=str(self._safety is not None).lower(),
            ),
            KeyValue(
                key='safety_fresh',
                value=str(safety_fresh).lower(),
            ),
            KeyValue(
                key='world_received',
                value=str(self._world is not None).lower(),
            ),
            KeyValue(
                key='world_fresh',
                value=str(world_fresh).lower(),
            ),
            KeyValue(
                key='motion_ready',
                value=str(status.motion_ready).lower(),
            ),
        ]
        diagnostics.status = [diagnostic]
        self._diagnostics.publish(diagnostics)

    @staticmethod
    def _is_fresh(message, received_steady, now_steady, timeout) -> bool:
        """Return true only for a received dependency inside its steady lease."""
        if message is None or received_steady is None:
            return False
        age = now_steady - received_steady
        return 0.0 <= age <= timeout


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
