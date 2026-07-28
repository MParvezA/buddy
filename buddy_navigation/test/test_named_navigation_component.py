import threading
import time
from unittest.mock import Mock, patch

from action_msgs.msg import GoalStatus
from buddy_interfaces.action import NavigateToNamedLocation
from buddy_interfaces.msg import SafetyState
from buddy_interfaces.srv import ResolveNamedLocation
from buddy_navigation import named_navigation_adapter
from buddy_navigation.named_navigation_adapter import (
    DrainingMultiThreadedExecutor,
    NamedNavigationAdapter,
)
from geometry_msgs.msg import TransformStamped
from nav2_msgs.action import NavigateToPose
import pytest
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster


def wait_future(future, timeout_sec=5.0):
    deadline = time.monotonic() + timeout_sec
    while not future.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert future.done()
    return future.result()


class FakeNavigationDependencies(Node):

    def __init__(self, *, block_navigation=False):
        super().__init__('fake_navigation_dependencies')
        self.block_navigation = block_navigation
        self.navigation_started = threading.Event()
        self.navigation_cancelled = threading.Event()
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
            cancel_callback=lambda _goal_handle: CancelResponse.ACCEPT,
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
        self.navigation_started.set()
        if self.block_navigation:
            while rclpy.ok() and not goal_handle.is_cancel_requested:
                time.sleep(0.01)
            if goal_handle.is_cancel_requested:
                self.navigation_cancelled.set()
                goal_handle.canceled()
                return NavigateToPose.Result()
            goal_handle.abort()
            return NavigateToPose.Result()
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


def test_shutdown_cancels_active_nav2_and_becomes_idle(monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    monkeypatch.setenv('ROS_DOMAIN_ID', '171')
    monkeypatch.setenv('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    rclpy.init()
    adapter = NamedNavigationAdapter()
    dependencies = FakeNavigationDependencies(block_navigation=True)
    client_node = rclpy.create_node('named_navigation_shutdown_client')
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
    goal_handle = None
    result_future = None
    try:
        assert client.wait_for_server(timeout_sec=2.0)
        precondition_deadline = time.monotonic() + 2.0
        while time.monotonic() < precondition_deadline:
            dependencies.publish_preconditions()
            if adapter._safety is not None and adapter._localization_available():
                break
            time.sleep(0.05)
        goal = NavigateToNamedLocation.Goal()
        goal.location_name = 'kitchen'
        goal_handle = wait_future(client.send_goal_async(goal))
        assert goal_handle.accepted
        result_future = goal_handle.get_result_async()
        assert dependencies.navigation_started.wait(2.0)

        concurrent_goal = wait_future(client.send_goal_async(goal))
        assert not concurrent_goal.accepted
        assert not adapter.shutdown_complete()
        adapter.request_shutdown()
        shutdown_deadline = time.monotonic() + adapter.shutdown_timeout_seconds()
        while (
            not adapter.shutdown_complete()
            and time.monotonic() < shutdown_deadline
        ):
            time.sleep(0.01)

        assert adapter.shutdown_complete()
        assert dependencies.navigation_cancelled.is_set()
        wrapped_result = wait_future(result_future)
        assert wrapped_result.result.outcome == (
            NavigateToNamedLocation.Result.OUTCOME_FAILED
        )
        assert wrapped_result.status == GoalStatus.STATUS_ABORTED
        assert 'Nav2 cancellation and stopped state confirmed' in (
            wrapped_result.result.message
        )
    finally:
        if (
            goal_handle is not None
            and result_future is not None
            and not result_future.done()
        ):
            wait_future(goal_handle.cancel_goal_async())
            wait_future(result_future)
        executor.shutdown()
        spin_thread.join(timeout=2.0)
        dependencies.nav2_server.destroy()
        for node in (adapter, dependencies, client_node):
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_executor_drain_reaps_completed_task_outcomes():
    future = Mock()
    future.cancelled.return_value = False
    future.done.return_value = True
    future.exception.return_value = None
    executor = object.__new__(DrainingMultiThreadedExecutor)
    executor._futures = [future]
    executor._sigint_gc = None

    cancelled = executor.drain_submitted_callbacks(timeout_sec=0.1)

    assert executor._futures == []
    assert cancelled == ()
    future.exception.assert_called_once_with()
    future.result.assert_called_once_with()


def test_executor_drain_surfaces_task_exception():
    error = RuntimeError('callback failed')
    future = Mock()
    future.cancelled.return_value = False
    future.done.return_value = True
    future.exception.return_value = error
    executor = object.__new__(DrainingMultiThreadedExecutor)
    executor._futures = [future]
    executor._sigint_gc = None

    with pytest.raises(RuntimeError, match='callback failed'):
        executor.drain_submitted_callbacks(timeout_sec=0.1)

    future.exception.assert_called_once_with()
    future.result.assert_not_called()


def test_executor_drain_cancels_queued_callback():
    future = Mock()
    future.cancelled.return_value = False
    future.done.return_value = False
    future.executing.return_value = False
    source = Mock(spec=[])
    executor = object.__new__(DrainingMultiThreadedExecutor)
    executor._futures = [future]
    executor._sigint_gc = None
    executor._tasks_lock = threading.Lock()
    executor._pending_tasks = {
        future: Mock(source_entity=source),
    }

    cancelled = executor.drain_submitted_callbacks(timeout_sec=0.1)

    assert executor._futures == []
    assert cancelled == ('unittest.mock.Mock',)
    future.cancel.assert_called_once_with()
    future.exception.assert_not_called()
    future.result.assert_not_called()


def test_executor_drain_times_out_for_unfinished_task():
    future = Mock()
    future.cancelled.return_value = False
    future.done.return_value = False
    future.executing.return_value = True
    executor = object.__new__(DrainingMultiThreadedExecutor)
    executor._futures = [future]
    executor._sigint_gc = None
    executor._tasks_lock = threading.Lock()
    executor._pending_tasks = {
        future: Mock(source_entity=Mock()),
    }

    with pytest.raises(
        TimeoutError,
        match='executor callbacks did not finish before shutdown',
    ):
        executor.drain_submitted_callbacks(timeout_sec=0.0)

    assert executor._futures == [future]
    future.exception.assert_not_called()
    future.result.assert_not_called()


def test_sigint_drains_active_navigation_before_executor_shutdown():
    events = []
    node = Mock()
    node.shutdown_complete.side_effect = [False, True]
    node.shutdown_timeout_seconds.return_value = 0.5
    node.request_shutdown.side_effect = lambda: events.append('request_shutdown')
    node.destroy_node.side_effect = lambda: events.append('destroy_node')
    executor = Mock()
    executor.spin.side_effect = KeyboardInterrupt()
    executor.spin_once.side_effect = lambda timeout_sec: events.append('spin_once')
    executor.drain_submitted_callbacks.side_effect = (
        lambda timeout_sec: (
            events.append('drain_submitted_callbacks'),
            (),
        )[1]
    )
    executor.shutdown.side_effect = lambda: events.append('executor_shutdown')
    with (
        patch.object(named_navigation_adapter.rclpy, 'init') as initialize,
        patch.object(named_navigation_adapter.rclpy, 'ok', return_value=True),
        patch.object(
            named_navigation_adapter.rclpy,
            'shutdown',
            side_effect=lambda: events.append('rclpy_shutdown'),
        ),
        patch.object(
            named_navigation_adapter,
            'NamedNavigationAdapter',
            return_value=node,
        ),
        patch.object(
            named_navigation_adapter,
            'DrainingMultiThreadedExecutor',
            return_value=executor,
        ),
    ):
        named_navigation_adapter.main(args=['--ros-args'])

    initialize.assert_called_once_with(
        args=['--ros-args'],
        signal_handler_options=SignalHandlerOptions.NO,
    )
    assert events == [
        'request_shutdown',
        'spin_once',
        'drain_submitted_callbacks',
        'executor_shutdown',
        'destroy_node',
        'rclpy_shutdown',
    ]


def test_destroy_node_destroys_owned_action_waitables_before_parent():
    events = []
    adapter = object.__new__(NamedNavigationAdapter)
    adapter._owned_entity_lock = threading.Lock()
    adapter._action_destroyed = False
    adapter._nav2_destroyed = False
    adapter._action = Mock()
    adapter._nav2 = Mock()
    adapter._action.destroy.side_effect = lambda: events.append('action_server')
    adapter._nav2.destroy.side_effect = lambda: events.append('action_client')

    with patch.object(
        Node,
        'destroy_node',
        side_effect=lambda: events.append('node'),
    ) as parent_destroy:
        adapter.destroy_node()
    adapter.destroy_owned_entities()

    assert events == ['action_server', 'action_client', 'node']
    adapter._action.destroy.assert_called_once_with()
    adapter._nav2.destroy.assert_called_once_with()
    parent_destroy.assert_called_once_with()
