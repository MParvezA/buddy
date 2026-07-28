"""Ingest frozen raw sensor topics and publish bounded readiness diagnostics."""

import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image, Imu, LaserScan

from .readiness_core import SensorTracker


DIAGNOSTICS_TOPIC = '/diagnostics'


def sensor_qos() -> QoSProfile:
    """Return the frozen lidar/IMU/camera QoS."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=5,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    )


class SensorReadinessNode(Node):
    """Validate only raw stream liveness; make no semantic recognition claims."""

    def __init__(self) -> None:
        super().__init__('sensor_readiness', namespace='/buddy')
        self.declare_parameter('sensor_timeout_sec', 1.0)
        self.declare_parameter('diagnostic_rate_hz', 1.0)
        self._tracker = SensorTracker()
        qos = sensor_qos()
        self.create_subscription(
            LaserScan, '/scan', lambda msg: self._observe('scan', msg), qos
        )
        self.create_subscription(
            Imu, '/imu/data_raw', lambda msg: self._observe('imu', msg), qos
        )
        self.create_subscription(
            Image, '/camera/image_raw', lambda msg: self._observe('image', msg), qos
        )
        self.create_subscription(
            CameraInfo,
            '/camera/camera_info',
            lambda msg: self._observe('camera_info', msg),
            qos,
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
        rate = max(float(self.get_parameter('diagnostic_rate_hz').value), 0.1)
        self.create_timer(1.0 / rate, self._publish_diagnostic)

    def _observe(self, sensor: str, message) -> None:
        self._tracker.observe(sensor, message.header.frame_id, time.monotonic())

    def _publish_diagnostic(self) -> None:
        readiness = self._tracker.readiness(
            time.monotonic(),
            float(self.get_parameter('sensor_timeout_sec').value),
        )
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = 'buddy/perception/raw_sensor_readiness'
        status.hardware_id = 'sensor_boundary'
        status.level = DiagnosticStatus.OK if readiness.ready else DiagnosticStatus.WARN
        status.message = (
            'raw sensor inputs ready'
            if readiness.ready
            else 'raw sensor inputs incomplete or stale'
        )
        status.values = [
            KeyValue(key='missing', value=','.join(readiness.missing)),
            KeyValue(key='stale', value=','.join(readiness.stale)),
            KeyValue(key='invalid_frames', value=','.join(readiness.invalid_frames)),
            KeyValue(key='semantic_recognition', value='not_configured'),
        ]
        array.status = [status]
        self._diagnostics.publish(array)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SensorReadinessNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
