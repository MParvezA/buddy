"""Publish the frozen Buddy world interfaces from a bounded semantic store."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from buddy_interfaces.msg import NamedLocation, WorldSummary
from buddy_interfaces.srv import ResolveNamedLocation
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener

from .store import Location, SemanticStore


SUMMARY_TOPIC = '/buddy/world/summary'
RESOLVE_SERVICE = '/buddy/world/resolve_named_location'
DIAGNOSTICS_TOPIC = '/diagnostics'


class WorldModelNode(Node):
    """Serve semantic poses and publish a low-rate transient world summary."""

    def __init__(self) -> None:
        super().__init__('world_model', namespace='/buddy')
        default_locations = str(
            Path(get_package_share_directory('buddy_world_model'))
            / 'config'
            / 'named_locations.yaml'
        )
        self.declare_parameter('locations_file', default_locations)
        self.declare_parameter('summary_rate_hz', 1.0)
        self.declare_parameter('max_observations', 50)
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')
        self._store = SemanticStore.from_yaml(
            self.get_parameter('locations_file').value,
            max_observations=int(self.get_parameter('max_observations').value),
        )
        summary_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        diagnostics_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._summary_pub = self.create_publisher(
            WorldSummary, SUMMARY_TOPIC, summary_qos
        )
        self._diagnostics = self.create_publisher(
            DiagnosticArray, DIAGNOSTICS_TOPIC, diagnostics_qos
        )
        self._resolve = self.create_service(
            ResolveNamedLocation, RESOLVE_SERVICE, self._resolve_location
        )
        self._tf_buffer = Buffer(node=self)
        self._tf_listener = TransformListener(self._tf_buffer, self)
        frequency = max(float(self.get_parameter('summary_rate_hz').value), 0.1)
        self.create_timer(1.0 / frequency, self._publish_summary)
        self._publish_diagnostic(DiagnosticStatus.OK, 'ready')

    def _to_message(self, location: Location) -> NamedLocation:
        message = NamedLocation()
        message.name = location.name
        message.enabled = location.enabled
        message.description = location.description
        message.pose.header.frame_id = 'map'
        message.pose.header.stamp = self.get_clock().now().to_msg()
        message.pose.pose.position.x = location.x
        message.pose.pose.position.y = location.y
        message.pose.pose.position.z = location.z
        message.pose.pose.orientation.x = location.qx
        message.pose.pose.orientation.y = location.qy
        message.pose.pose.orientation.z = location.qz
        message.pose.pose.orientation.w = location.qw
        return message

    def _resolve_location(self, request, response):
        location = self._store.resolve(request.name)
        if location is None or not location.enabled:
            response.found = False
            response.message = f'unknown or disabled named location: {request.name}'
            return response
        response.found = True
        response.location = self._to_message(location)
        response.message = 'named location resolved'
        return response

    def _publish_summary(self) -> None:
        summary = WorldSummary()
        summary.header.stamp = self.get_clock().now().to_msg()
        summary.header.frame_id = 'map'
        summary.named_locations = [
            self._to_message(location) for location in self._store.locations
        ]
        summary.objects = list(self._store.observations)
        try:
            transform = self._tf_buffer.lookup_transform(
                self.get_parameter('map_frame').value,
                self.get_parameter('base_frame').value,
                Time(),
                timeout=Duration(seconds=0.05),
            )
            summary.robot_pose_valid = True
            summary.robot_pose.header = transform.header
            summary.robot_pose.pose.position.x = transform.transform.translation.x
            summary.robot_pose.pose.position.y = transform.transform.translation.y
            summary.robot_pose.pose.position.z = transform.transform.translation.z
            summary.robot_pose.pose.orientation = transform.transform.rotation
            summary.current_location = self._nearest_location(
                transform.transform.translation.x,
                transform.transform.translation.y,
            )
        except TransformException:
            summary.robot_pose_valid = False
            summary.current_location = ''
        self._summary_pub.publish(summary)

    def _nearest_location(self, x: float, y: float) -> str:
        candidates = [
            ((location.x - x) ** 2 + (location.y - y) ** 2, location.name)
            for location in self._store.locations
            if location.enabled
        ]
        if not candidates:
            return ''
        distance_squared, name = min(candidates)
        return name if distance_squared <= 0.5 ** 2 else ''

    def _publish_diagnostic(self, level: int, message: str) -> None:
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = 'buddy/world_model'
        status.hardware_id = 'software'
        status.level = level
        status.message = message
        status.values = [
            KeyValue(key='named_locations', value=str(len(self._store.locations))),
            KeyValue(key='observation_capacity', value=str(
                self.get_parameter('max_observations').value
            )),
        ]
        array.status = [status]
        self._diagnostics.publish(array)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = WorldModelNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
