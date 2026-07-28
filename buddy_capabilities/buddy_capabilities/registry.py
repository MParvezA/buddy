"""ROS service exposing the frozen capability catalogue."""

from buddy_capabilities.catalog import CAPABILITIES
from buddy_interfaces.action import NavigateToNamedLocation, Speak
from buddy_interfaces.msg import CapabilityArgument, CapabilityDescriptor, RobotStatus
from buddy_interfaces.srv import ListCapabilities
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class CapabilityRegistry(Node):
    """Advertise exact schemas and current endpoint-derived availability."""

    def __init__(self):
        super().__init__('capability_registry', namespace='/buddy')
        # ROS 2 declares use_sim_time automatically; accepting that standard
        # parameter keeps this node simulation-time compatible.
        self._status_seen = False
        status_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                                durability=DurabilityPolicy.TRANSIENT_LOCAL)
        diagnostics_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                                     durability=DurabilityPolicy.VOLATILE)
        self._status_subscription = self.create_subscription(
            RobotStatus, '/buddy/status', self._status_callback, status_qos)
        self._speak_client = ActionClient(self, Speak, '/buddy/voice/speak')
        self._navigate_client = ActionClient(
            self, NavigateToNamedLocation,
            '/buddy/navigation/navigate_to_named_location')
        self._service = self.create_service(
            ListCapabilities, '/buddy/capabilities/list', self._list_capabilities)
        self._diagnostics = self.create_publisher(DiagnosticArray, '/diagnostics', diagnostics_qos)
        self._timer = self.create_timer(1.0, self._publish_diagnostics)

    def _status_callback(self, _message: RobotStatus) -> None:
        self._status_seen = True

    def _available(self, name: str) -> tuple[bool, str]:
        if name == 'stop':
            return True, ''
        if name == 'speak':
            return self._endpoint_available(self._speak_client, 'speech action unavailable')
        if name == 'navigate_to':
            return self._endpoint_available(self._navigate_client, 'navigation action unavailable')
        return (self._status_seen, 'robot status unavailable' if not self._status_seen else '')

    @staticmethod
    def _endpoint_available(client: ActionClient, reason: str) -> tuple[bool, str]:
        available = client.server_is_ready()
        return available, '' if available else reason

    def _list_capabilities(self, _request, response):
        response.capabilities = [self._descriptor(capability) for capability in CAPABILITIES]
        return response

    def _descriptor(self, capability):
        available, reason = self._available(capability.name)
        descriptor = CapabilityDescriptor()
        descriptor.name = capability.name
        descriptor.version = '0.1.0'
        descriptor.description = capability.description
        descriptor.arguments = [self._argument(argument) for argument in capability.arguments]
        descriptor.available = available
        descriptor.unavailable_reason = reason
        descriptor.requires_motion = capability.requires_motion
        descriptor.requires_localization = capability.requires_localization
        descriptor.requires_confirmation = capability.requires_confirmation
        return descriptor

    @staticmethod
    def _argument(argument):
        message = CapabilityArgument()
        message.name = argument.name
        message.value_type = argument.value_type
        message.required = argument.required
        message.description = argument.description
        message.default_value = argument.default_value
        message.allowed_values = list(argument.allowed_values)
        return message

    def _publish_diagnostics(self) -> None:
        status = DiagnosticStatus()
        status.name = 'buddy_capability_registry'
        status.hardware_id = 'buddy'
        status.level = DiagnosticStatus.OK
        status.message = 'capability registry active'
        status.values = [KeyValue(key='registered_count', value=str(len(CAPABILITIES)))]
        message = DiagnosticArray()
        message.header.stamp = self.get_clock().now().to_msg()
        message.status = [status]
        self._diagnostics.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CapabilityRegistry()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
