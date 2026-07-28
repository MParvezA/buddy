#!/usr/bin/env python3
"""Prove production controller-heartbeat loss faults safety and stops motion."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import time

from buddy_interfaces.msg import RobotStatus, SafetyState
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


CONTROLLER_DIAGNOSTIC_NAME = 'buddy_base_controller'


def _find_adapter_pid() -> int:
    candidates = []
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            command = (process / 'cmdline').read_bytes().decode(
                errors='replace'
            ).replace('\x00', ' ')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if 'buddy_gazebo' in command and 'safe_cmd_vel_adapter' in command:
            candidates.append(int(process.name))
    if len(candidates) != 1:
        raise RuntimeError(
            'expected one safe_cmd_vel_adapter process, got '
            + repr(candidates)
        )
    return candidates[0]


class ControllerHealthLossProbe(Node):
    """Drive only the registered teleop source and observe frozen safety state."""

    def __init__(self) -> None:
        super().__init__(
            'controller_health_loss_probe',
            parameter_overrides=[Parameter('use_sim_time', value=True)],
        )
        motion_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        state_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        diagnostics_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.teleop = self.create_publisher(
            TwistStamped,
            '/buddy/motion/request/teleop',
            motion_qos,
        )
        self.safe_commands: list[TwistStamped] = []
        self.safety: SafetyState | None = None
        self.status: RobotStatus | None = None
        self.controller_ok_seen = False
        self.create_subscription(
            TwistStamped,
            '/buddy/motion/safe_cmd_vel',
            self.safe_commands.append,
            motion_qos,
        )
        self.create_subscription(
            SafetyState,
            '/buddy/safety/state',
            self._on_safety,
            state_qos,
        )
        self.create_subscription(
            RobotStatus,
            '/buddy/status',
            self._on_status,
            state_qos,
        )
        self.create_subscription(
            DiagnosticArray,
            '/diagnostics',
            self._on_diagnostics,
            diagnostics_qos,
        )

    def _on_safety(self, message: SafetyState) -> None:
        self.safety = message

    def _on_status(self, message: RobotStatus) -> None:
        self.status = message

    def _on_diagnostics(self, message: DiagnosticArray) -> None:
        self.controller_ok_seen = self.controller_ok_seen or any(
            status.name == CONTROLLER_DIAGNOSTIC_NAME
            and status.level == DiagnosticStatus.OK
            for status in message.status
        )

    def publish_teleop(self) -> None:
        command = TwistStamped()
        command.header.stamp = self.get_clock().now().to_msg()
        command.header.frame_id = 'base_link'
        command.twist.linear.x = 0.18
        self.teleop.publish(command)

    def spin_until(
        self,
        predicate,
        timeout: float,
        *,
        publish_teleop: bool = False,
    ) -> float:
        started = time.monotonic()
        deadline = started + timeout
        while time.monotonic() < deadline:
            if publish_teleop:
                self.publish_teleop()
            rclpy.spin_once(self, timeout_sec=0.02)
            if predicate():
                return time.monotonic() - started
        raise AssertionError('timed out waiting for controller-health state')


def main() -> None:
    """Kill the sole adapter and prove the production safety fault path."""
    rclpy.init()
    node = ControllerHealthLossProbe()
    try:
        node.spin_until(
            lambda: (
                node.get_clock().now().nanoseconds > 0
                and node.controller_ok_seen
                and node.safety is not None
                and node.safety.motion_permitted
                and node.status is not None
                and node.status.motion_ready
            ),
            15.0,
            publish_teleop=True,
        )
        node.spin_until(
            lambda: any(
                abs(command.twist.linear.x) > 0.05
                for command in node.safe_commands
            ),
            2.0,
            publish_teleop=True,
        )

        node.safe_commands.clear()
        os.kill(_find_adapter_pid(), signal.SIGTERM)
        fault_elapsed = node.spin_until(
            lambda: (
                node.safety is not None
                and node.safety.state == SafetyState.STATE_FAULT
                and node.safety.reason_code
                == SafetyState.REASON_CONTROLLER_FAULT
                and not node.safety.motion_permitted
                and len(node.safe_commands) >= 3
                and all(
                    abs(command.twist.linear.x) < 1.0e-9
                    and abs(command.twist.angular.z) < 1.0e-9
                    for command in node.safe_commands[-3:]
                )
            ),
            1.5,
            publish_teleop=True,
        )
        node.spin_until(
            lambda: node.status is not None and not node.status.motion_ready,
            1.0,
            publish_teleop=True,
        )
        assert fault_elapsed <= 1.0, (
            'controller-health stop exceeded bound: '
            f'{fault_elapsed:.3f} s'
        )
        print(
            'Buddy controller-health loss passed: adapter heartbeat expired, '
            f'safety faulted and safe output reached zero in '
            f'{fault_elapsed:.3f} s, RobotStatus inhibited motion '
            f'(ROS_DOMAIN_ID={os.environ.get("ROS_DOMAIN_ID", "")})'
        )
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
