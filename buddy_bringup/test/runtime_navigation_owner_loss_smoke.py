#!/usr/bin/env python3
"""Prove named-navigation owner loss closes persistent private motion input."""

import os
from pathlib import Path
import signal
import time

from action_msgs.srv import CancelGoal
from buddy_interfaces.action import NavigateToNamedLocation
from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy


PRIVATE_NAV2_TOPIC = '/buddy/navigation/cmd_vel_smoothed'
NAVIGATION_REQUEST_TOPIC = '/buddy/motion/request/navigation'
SAFE_COMMAND_TOPIC = '/buddy/motion/safe_cmd_vel'


def _moving(message: TwistStamped) -> bool:
    return (
        abs(message.twist.linear.x) > 0.01
        or abs(message.twist.angular.z) > 0.01
    )


def _find_named_adapter_pid() -> int:
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
        if (
            'buddy_navigation' in command
            and 'named_navigation_adapter' in command
        ):
            candidates.append(int(process.name))
    if len(candidates) != 1:
        raise RuntimeError(
            'expected one named_navigation_adapter process, got '
            + repr(candidates)
        )
    return candidates[0]


class OwnerLossProbe(Node):
    """Observe the three motion boundaries without publishing velocity."""

    def __init__(self):
        super().__init__('navigation_owner_loss_probe')
        self.navigation_requests = []
        self.private_nav2_commands = []
        self.safe_commands = []
        command_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        motion_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.create_subscription(
            TwistStamped,
            PRIVATE_NAV2_TOPIC,
            self.private_nav2_commands.append,
            command_qos,
        )
        self.create_subscription(
            TwistStamped,
            NAVIGATION_REQUEST_TOPIC,
            self.navigation_requests.append,
            motion_qos,
        )
        self.create_subscription(
            TwistStamped,
            SAFE_COMMAND_TOPIC,
            self.safe_commands.append,
            motion_qos,
        )
        self.private_command_publisher = self.create_publisher(
            TwistStamped,
            PRIVATE_NAV2_TOPIC,
            command_qos,
        )
        self.client = ActionClient(
            self,
            NavigateToNamedLocation,
            '/buddy/navigation/navigate_to_named_location',
        )
        self.nav2_cancel = self.create_client(
            CancelGoal,
            '/navigate_to_pose/_action/cancel_goal',
        )

    def publish_private_command(self) -> None:
        """Inject the command a surviving Nav2 process could keep producing."""
        command = TwistStamped()
        command.twist.linear.x = 0.2
        self.private_command_publisher.publish(command)

    def spin_until(
        self,
        predicate,
        timeout: float,
        *,
        publish_private: bool = False,
    ) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if publish_private:
                self.publish_private_command()
            rclpy.spin_once(self, timeout_sec=0.02)
            if predicate():
                return True
        return False

    def cancel_nav2_for_test_cleanup(self) -> None:
        """Cancel all Nav2 goals after the owner-loss assertion has completed."""
        if not self.nav2_cancel.wait_for_service(timeout_sec=2.0):
            return
        future = self.nav2_cancel.call_async(CancelGoal.Request())
        self.spin_until(future.done, 2.0)


def main() -> None:
    node = None
    rclpy.init()
    try:
        node = OwnerLossProbe()
        assert node.client.wait_for_server(
            timeout_sec=15.0
        ), 'named navigation action is unavailable'
        goal = NavigateToNamedLocation.Goal()
        goal.location_name = 'kitchen'
        submission = node.client.send_goal_async(goal)
        assert node.spin_until(
            submission.done, 5.0
        ), 'named navigation submission timed out'
        handle = submission.result()
        assert handle.accepted, 'named navigation goal was rejected'
        assert node.spin_until(
            lambda: any(_moving(message) for message in node.navigation_requests),
            20.0,
        ), 'navigation never produced a nonzero owned motion request'

        node.navigation_requests.clear()
        node.private_nav2_commands.clear()
        node.safe_commands.clear()
        adapter_pid = _find_named_adapter_pid()
        owner_lost_at = time.monotonic()
        os.kill(adapter_pid, signal.SIGTERM)

        assert node.spin_until(
            lambda: any(
                _moving(message) for message in node.private_nav2_commands
            ),
            0.30,
            publish_private=True,
        ), 'persistent private Nav2 command stimulus was not observed'
        assert node.spin_until(
            lambda: any(
                not _moving(message) for message in node.navigation_requests
            ),
            0.30,
            publish_private=True,
        ), 'navigation ownership lease did not emit zero within its bound'
        lease_elapsed = time.monotonic() - owner_lost_at
        zero_index = next(
            index
            for index, message in enumerate(node.navigation_requests)
            if not _moving(message)
        )
        assert node.spin_until(
            lambda: (
                len(node.safe_commands) >= 3
                and all(
                    not _moving(message)
                    for message in node.safe_commands[-3:]
                )
            ),
            1.0,
            publish_private=True,
        ), 'safe command did not settle at zero after owner loss'
        safe_stop_elapsed = time.monotonic() - owner_lost_at
        assert lease_elapsed <= 0.30, (
            'navigation owner-loss stop exceeded bound: '
            f'{lease_elapsed:.3f} s'
        )
        assert all(
            not _moving(message)
            for message in node.navigation_requests[zero_index:]
        ), 'navigation request reopened without a new owned action'
        assert safe_stop_elapsed <= 1.30, (
            'acceleration-limited safe stop exceeded bound: '
            f'{safe_stop_elapsed:.3f} s'
        )
        print(
            'Buddy navigation owner-loss passed: '
            f'private Nav2 remained active, authorization closed in '
            f'{lease_elapsed:.3f} s, safe output decelerated to zero in '
            f'{safe_stop_elapsed:.3f} s '
            f'(ROS_DOMAIN_ID={os.environ.get("ROS_DOMAIN_ID", "")})'
        )
        node.cancel_nav2_for_test_cleanup()
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
