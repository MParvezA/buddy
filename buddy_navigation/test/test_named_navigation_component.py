import threading
import time

from buddy_interfaces.action import NavigateToNamedLocation
from buddy_interfaces.msg import SafetyState
from buddy_interfaces.srv import ResolveNamedLocation
from buddy_navigation.named_navigation_adapter import NamedNavigationAdapter
from geometry_msgs.msg import TransformStamped
from nav2_msgs.action import NavigateToPose
import rclpy
from rclpy.action import ActionClient, ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster


def wait_future(future, timeout_sec=5.0):
    deadline = time.monotonic() + timeout_sec
    while not future.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert future.done()
    return future.result()


class FakeNavigationDependencies(Node):

    def __init__(self):
        super().__init__('fake_navigation_dependencies')
        group = ReentrantCallbackGroup()
        self.create_service(
            ResolveNamedLocation,
            '/buddy/world/resolve_named_location',
            self._resolve,
            callback_group=group,
        )
        self.nav2_server = ActionServer(
            self,
            NavigateToPose,
            '/navigate_to_pose',
            execute_callback=self._navigate,
            callback_group=group,
        )
        safety_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.safety = self.create_publisher(
            SafetyState, '/buddy/safety/state', safety_qos
        )
        self.tf = StaticTransformBroadcaster(self)

    def publish_preconditions(self):
        safety = SafetyState()
        safety.state = SafetyState.STATE_NORMAL
        safety.motion_permitted = True
        self.safety.publish(safety)
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = 'map'
        transform.child_frame_id = 'base_link'
        transform.transform.rotation.w = 1.0
        self.tf.sendTransform(transform)

    def _resolve(self, request, response):
        response.found = request.name == 'kitchen'
        response.location.name = request.name
        response.location.enabled = response.found
        response.location.pose.header.frame_id = 'map'
        response.location.pose.pose.orientation.w = 1.0
        response.message = 'resolved'
        return response

    def _navigate(self, goal_handle):
        goal_handle.succeed()
        return NavigateToPose.Result()


def test_named_action_uses_rclpy_executor_without_asyncio(monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    monkeypatch.setenv('ROS_DOMAIN_ID', '171')
    monkeypatch.setenv('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    rclpy.init()
    adapter = NamedNavigationAdapter()
    dependencies = FakeNavigationDependencies()
    client_node = rclpy.create_node('named_navigation_component_client')
    client = ActionClient(
        client_node,
        NavigateToNamedLocation,
        '/buddy/navigation/navigate_to_named_location',
    )
    executor = MultiThreadedExecutor(num_threads=6)
    for node in (adapter, dependencies, client_node):
        executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    try:
        assert client.wait_for_server(timeout_sec=2.0)
        precondition_deadline = time.monotonic() + 2.0
        while time.monotonic() < precondition_deadline:
            dependencies.publish_preconditions()
            if adapter._safety is not None and adapter._localization_available():
                break
            time.sleep(0.05)
        assert adapter._safety is not None
        assert adapter._localization_available()
        goal = NavigateToNamedLocation.Goal()
        goal.location_name = 'kitchen'
        goal_handle = wait_future(client.send_goal_async(goal))
        assert goal_handle.accepted
        wrapped_result = wait_future(goal_handle.get_result_async())
        assert wrapped_result.result.outcome == (
            NavigateToNamedLocation.Result.OUTCOME_SUCCEEDED
        )
    finally:
        executor.shutdown()
        spin_thread.join(timeout=2.0)
        dependencies.nav2_server.destroy()
        for node in (adapter, dependencies, client_node):
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
