#!/usr/bin/env python3
"""Prove adapter process loss cannot leave Buddy moving."""
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy


class WatchdogProbe(Node):
    def __init__(self):
        super().__init__('buddy_gazebo_watchdog_probe')
        self.position = None
        self.publisher = self.create_publisher(
            TwistStamped,
            '/buddy/motion/safe_cmd_vel',
            QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE),
        )
        self.create_subscription(
            Odometry,
            '/odom/wheel',
            self._odom,
            QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT),
        )

    def _odom(self, message):
        self.position = (message.pose.pose.position.x, message.pose.pose.position.y)

    def publish_forward(self):
        command = TwistStamped()
        command.header.stamp = self.get_clock().now().to_msg()
        command.twist.linear.x = 0.25
        self.publisher.publish(command)


def distance(start, end):
    return math.hypot(end[0] - start[0], end[1] - start[1])


def spin_for(node, duration, publish=False):
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        if publish:
            node.publish_forward()
        rclpy.spin_once(node, timeout_sec=0.04)


def find_adapter_pid(launch_pid):
    deadline = time.monotonic() + 15.0
    children_file = Path(f'/proc/{launch_pid}/task/{launch_pid}/children')
    while time.monotonic() < deadline:
        if children_file.exists():
            for child in children_file.read_text().split():
                cmdline = Path(f'/proc/{child}/cmdline')
                if cmdline.exists() and 'safe_cmd_vel_adapter' in cmdline.read_bytes().decode(
                        errors='replace').replace('\x00', ' '):
                    return int(child)
        time.sleep(0.1)
    raise RuntimeError('safe_cmd_vel_adapter child process not found')


def main():
    isolated_domain = str(100 + os.getpid() % 50)
    isolated_partition = f'buddy_watchdog_{os.getpid()}'
    os.environ['ROS_DOMAIN_ID'] = isolated_domain
    os.environ['GZ_PARTITION'] = isolated_partition
    launch_log = Path(tempfile.gettempdir()) / f'buddy-watchdog-{os.getpid()}.log'
    with launch_log.open('w') as output:
        launch = subprocess.Popen(
            ['ros2', 'launch', 'buddy_gazebo', 'buddy_sim.launch.py'],
            env=os.environ.copy(),
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )

    node = None
    try:
        rclpy.init()
        node = WatchdogProbe()
        odom_deadline = time.monotonic() + 15.0
        while node.position is None and time.monotonic() < odom_deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
        assert node.position is not None, 'no wheel odometry received'
        moving_start = node.position
        spin_for(node, 2.0, publish=True)
        moving_distance = distance(moving_start, node.position)
        assert moving_distance > 0.15, (
            f'nonzero command did not move Buddy: {moving_distance:.3f} m')

        adapter_pid = find_adapter_pid(launch.pid)
        os.kill(adapter_pid, signal.SIGTERM)
        loss_start = node.position
        # Keep publishing to prove the command path is broken specifically by
        # adapter loss, then allow the in-Gazebo watchdog timeout to expire.
        spin_for(node, 1.5, publish=True)
        settle_position = node.position
        spin_for(node, 1.0, publish=True)
        stopped_distance = distance(settle_position, node.position)
        assert stopped_distance < 0.02, (
            'Buddy kept moving after adapter loss: '
            f'{stopped_distance:.3f} m after timeout '
            f'(initial post-loss travel {distance(loss_start, settle_position):.3f} m)')
        print(
            'Buddy Gazebo watchdog passed '
            f'(moved={moving_distance:.3f} m, stopped_delta={stopped_distance:.3f} m, '
            f'ROS_DOMAIN_ID={isolated_domain}, GZ_PARTITION={isolated_partition})')
    except Exception:
        print(launch_log.read_text()[-8000:], file=sys.stderr)
        raise
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        if launch.poll() is None:
            launch.send_signal(signal.SIGINT)
        try:
            launch.wait(timeout=15)
        except subprocess.TimeoutExpired:
            launch.terminate()
            launch.wait(timeout=5)


if __name__ == '__main__':
    main()
