#!/usr/bin/env python3
"""Exercise Buddy's bridged sensor, clock, odometry, and static-TF contract."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image, Imu, LaserScan
from tf2_msgs.msg import TFMessage


EXPECTED_SENSOR_FRAMES = {
    'scan': 'lidar_link',
    'imu': 'imu_link',
    'camera_image': 'camera_optical_frame',
    'camera_info': 'camera_optical_frame',
}
EXPECTED_STATIC_TF = {
    ('base_link', 'base_footprint'),
    ('base_link', 'lidar_link'),
    ('base_link', 'imu_link'),
    ('base_link', 'camera_link'),
    ('camera_link', 'camera_optical_frame'),
}


class ContractProbe(Node):
    def __init__(self):
        super().__init__('buddy_gazebo_contract_probe')
        sensor_qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
        transient_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.frames = {}
        self.odom_frames = None
        self.clock_samples = []
        self.clock_regression = None
        self.static_tf = set()
        self.dynamic_tf = set()
        self.odom_qos = None
        self.create_subscription(LaserScan, '/scan', self._scan, sensor_qos)
        self.create_subscription(Imu, '/imu/data_raw', self._imu, sensor_qos)
        self.create_subscription(Image, '/camera/image_raw', self._image, sensor_qos)
        self.create_subscription(
            CameraInfo, '/camera/camera_info', self._camera_info, sensor_qos)
        self.create_subscription(Odometry, '/odom/wheel', self._odom, sensor_qos)
        self.create_subscription(Clock, '/clock', self._on_clock, sensor_qos)
        self.create_subscription(TFMessage, '/tf_static', self._tf_static, transient_qos)
        self.create_subscription(TFMessage, '/tf', self._tf_dynamic, sensor_qos)

    def _scan(self, message):
        self.frames['scan'] = message.header.frame_id

    def _imu(self, message):
        self.frames['imu'] = message.header.frame_id

    def _image(self, message):
        self.frames['camera_image'] = message.header.frame_id

    def _camera_info(self, message):
        self.frames['camera_info'] = message.header.frame_id

    def _odom(self, message):
        self.odom_frames = (message.header.frame_id, message.child_frame_id)

    def _on_clock(self, message):
        stamp = message.clock.sec * 1_000_000_000 + message.clock.nanosec
        if self.clock_samples and stamp < self.clock_samples[-1]:
            self.clock_regression = (self.clock_samples[-1], stamp)
        self.clock_samples.append(stamp)

    def _tf_static(self, message):
        self.static_tf.update(
            (transform.header.frame_id, transform.child_frame_id)
            for transform in message.transforms
        )

    def _tf_dynamic(self, message):
        self.dynamic_tf.update(
            (transform.header.frame_id, transform.child_frame_id)
            for transform in message.transforms
        )

    def complete(self):
        publisher_info = self.get_publishers_info_by_topic('/odom/wheel')
        if publisher_info:
            self.odom_qos = publisher_info[0].qos_profile
        return (
            set(self.frames) == set(EXPECTED_SENSOR_FRAMES)
            and self.odom_frames is not None
            and len(self.clock_samples) >= 5
            and EXPECTED_STATIC_TF <= self.static_tf
            and self.odom_qos is not None
        )

    def assert_contract(self):
        failures = []
        if self.frames != EXPECTED_SENSOR_FRAMES:
            failures.append(
                f'sensor frames: expected {EXPECTED_SENSOR_FRAMES}, got {self.frames}')
        if self.odom_frames != ('odom', 'base_link'):
            failures.append(
                f'odom frames: expected (odom, base_link), got {self.odom_frames}')
        expected_odom_qos = (
            HistoryPolicy.KEEP_LAST,
            10,
            ReliabilityPolicy.BEST_EFFORT,
            DurabilityPolicy.VOLATILE,
        )
        actual_odom_qos = None if self.odom_qos is None else (
            self.odom_qos.history,
            self.odom_qos.depth,
            self.odom_qos.reliability,
            self.odom_qos.durability,
        )
        # DDS discovery does not transmit writer history/depth on all RMW
        # implementations. In that case they are UNKNOWN/0; the companion
        # bridge_qos_config C++ test asserts ros_gz_bridge resolves the actual
        # publisher construction to KeepLast(10).
        undiscoverable_depth = (
            HistoryPolicy.UNKNOWN,
            0,
            ReliabilityPolicy.BEST_EFFORT,
            DurabilityPolicy.VOLATILE,
        )
        if actual_odom_qos not in (expected_odom_qos, undiscoverable_depth):
            failures.append(
                f'odom QoS: expected {expected_odom_qos}, got {actual_odom_qos}')
        if self.clock_regression is not None:
            failures.append(f'/clock moved backwards: {self.clock_regression}')
        if len(self.clock_samples) < 5:
            failures.append(f'not enough /clock samples: {len(self.clock_samples)}')
        elif self.clock_samples[-1] <= self.clock_samples[0]:
            failures.append(f'/clock did not advance: {self.clock_samples}')
        missing_tf = EXPECTED_STATIC_TF - self.static_tf
        if missing_tf:
            failures.append(f'missing static TF: {missing_tf}')
        if ('odom', 'base_link') in self.static_tf | self.dynamic_tf:
            failures.append(
                'Gazebo fragment published contract-owned odom -> base_link TF')
        conceptual_edges = self.static_tf | self.dynamic_tf
        if self.odom_frames == ('odom', 'base_link'):
            conceptual_edges.add(('odom', 'base_link'))
        parents = {}
        for parent, child in conceptual_edges:
            parents.setdefault(child, set()).add(parent)
        duplicate_parents = {
            child: values for child, values in parents.items() if len(values) > 1}
        if duplicate_parents:
            failures.append(f'TF children with multiple parents: {duplicate_parents}')
        required_chain = {
            ('odom', 'base_link'),
            ('base_link', 'base_footprint'),
            ('base_link', 'lidar_link'),
            ('base_link', 'imu_link'),
            ('base_link', 'camera_link'),
        }
        missing_chain = required_chain - conceptual_edges
        if missing_chain:
            failures.append(f'missing conceptual TF chain edges: {missing_chain}')
        assert not failures, '; '.join(failures)


def main():
    isolated_domain = str(150 + os.getpid() % 50)
    isolated_partition = f'buddy_contract_{os.getpid()}'
    os.environ['ROS_DOMAIN_ID'] = isolated_domain
    os.environ['GZ_PARTITION'] = isolated_partition
    launch_log = Path(tempfile.gettempdir()) / f'buddy-contract-{os.getpid()}.log'
    environment = os.environ.copy()
    with launch_log.open('w') as output:
        launch = subprocess.Popen(
            ['ros2', 'launch', 'buddy_gazebo', 'buddy_sim.launch.py'],
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )

    node = None
    try:
        rclpy.init()
        node = ContractProbe()
        deadline = time.monotonic() + 35.0
        while time.monotonic() < deadline and not node.complete():
            rclpy.spin_once(node, timeout_sec=0.2)
        node.assert_contract()
        print(
            'Buddy runtime contract passed '
            f'(ROS_DOMAIN_ID={isolated_domain}, GZ_PARTITION={isolated_partition})')
    except Exception:
        print(launch_log.read_text()[-8000:], file=sys.stderr)
        raise
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        launch.send_signal(signal.SIGINT)
        try:
            launch.wait(timeout=15)
        except subprocess.TimeoutExpired:
            launch.terminate()
            launch.wait(timeout=5)


if __name__ == '__main__':
    main()
