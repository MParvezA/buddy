"""The sole ROS-to-Gazebo motion boundary for the native Harmonic drive."""
from gz.msgs10.twist_pb2 import Twist
from gz.transport13 import Node as GzNode
import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy


class SafeCommandAdapter(Node):
    """Forward frozen safe command output to Gazebo's native DiffDrive plugin."""

    def __init__(self):
        super().__init__('safe_cmd_vel_adapter')
        # rclpy declares the standard simulation-time parameter. Keep this
        # fallback for runtimes that do not, without redeclaring it on Jazzy.
        if not self.has_parameter('use_sim_time'):
            self.declare_parameter('use_sim_time', False)
        self.declare_parameter('gz_topic', '/model/buddy/cmd_vel')
        self._gz_node = GzNode()
        self._publisher = self._gz_node.advertise(
            self.get_parameter('gz_topic').value, Twist)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(
            TwistStamped, '/buddy/motion/safe_cmd_vel', self._on_command, qos)

    def _on_command(self, command: TwistStamped) -> None:
        message = Twist()
        message.linear.x = command.twist.linear.x
        message.angular.z = command.twist.angular.z
        self._publisher.publish(message)


def main() -> None:
    rclpy.init()
    node = SafeCommandAdapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
