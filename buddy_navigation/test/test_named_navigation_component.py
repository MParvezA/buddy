import threading
import time
from types import SimpleNamespace
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


class ImmediateFuture:

    def __init__(self, value=None, *, error=None):
        self._value = value
        self._error = error

    def done(self):
        return True

    def exception(self):
        return self._error

    def result(self):
        if self._error is not None:
            raise self._error
        return self._value


class FakeAcceptedNav2Goal:

    accepted = True

    def __init__(self, result_future, *, cancel_error=None):
        self._result_future = result_future
        self._cancel_error = cancel_error
        self.cancel_calls = 0
        self.command_active = True

    def get_result_async(self):
        return self._result_future

    def cancel_goal_async(self):
        self.cancel_calls += 1
        self.command_active = False
        return ImmediateFuture(
            SimpleNamespace(goals_canceling=[object()]),
            error=self._cancel_error,
        )


def make_unit_adapter(nav_handle):
    adapter = object.__new__(NamedNavigationAdapter)
    adapter._latest_pose = None
    adapter._shutdown_requested = threading.Event()
    adapter._goal_lock = threading.Lock()
    adapter._goal_reserved = True
    adapter._execution_idle = threading.Event()
    adapter._delegated_goal_lock = threading.Lock()
    adapter._delegated_nav_handle = None
    adapter._delegated_result_future = None
    adapter._delegated_cancel_timeout = 0.1
    adapter._send_feedback = Mock()
    adapter._publish_diagnostic = Mock()
    adapter.get_logger = Mock(return_value=Mock())
    adapter.get_parameter = Mock(
        side_effect=lambda name: SimpleNamespace(
            value=0.1 if name == 'dependency_timeout_sec' else 10.0
        )
    )

    response = ResolveNamedLocation.Response()
    response.found = True
    response.location.enabled = True
    response.location.pose.header.frame_id = 'map'
    response.location.pose.pose.orientation.w = 1.0
    adapter._resolver = Mock()
    adapter._resolver.wait_for_service.return_value = True
    adapter._resolver.call_async.return_value = ImmediateFuture(response)
    adapter._localization_available = Mock(return_value=True)
    adapter._safety = SafetyState()
    adapter._motion_permitted = Mock(return_value=True)
    adapter._nav2 = Mock()
    adapter._nav2.wait_for_server.return_value = True
    adapter._nav2.send_goal_async.return_value = ImmediateFuture(nav_handle)

    goal_handle = Mock()
    goal_handle.request = SimpleNamespace(location_name='kitchen')
    goal_handle.is_cancel_requested = False
    return adapter, goal_handle


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
        assert wrapped_result.status == GoalStatus.STATUS_SUCCEEDED
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


def test_unexpected_execute_failure_aborts_with_custom_failure_result(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    monkeypatch.setenv('ROS_DOMAIN_ID', '172')
    monkeypatch.setenv('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    rclpy.init()
    adapter = NamedNavigationAdapter()
    adapter._execute_goal = Mock(
        side_effect=RuntimeError('injected adapter failure')
    )
    client_node = rclpy.create_node('named_navigation_failure_client')
    client = ActionClient(
        client_node,
        NavigateToNamedLocation,
        '/buddy/navigation/navigate_to_named_location',
    )
    executor = MultiThreadedExecutor(num_threads=4)
    for node in (adapter, client_node):
        executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    try:
        assert client.wait_for_server(timeout_sec=2.0)
        goal = NavigateToNamedLocation.Goal()
        goal.location_name = 'kitchen'
        goal_handle = wait_future(client.send_goal_async(goal))
        assert goal_handle.accepted

        wrapped_result = wait_future(goal_handle.get_result_async())

        assert wrapped_result.status == GoalStatus.STATUS_ABORTED
        assert wrapped_result.result.outcome == (
            NavigateToNamedLocation.Result.OUTCOME_FAILED
        )
        assert wrapped_result.result.message
        assert 'injected adapter failure' in wrapped_result.result.message
        assert adapter._goal_reserved is False
        assert adapter.shutdown_complete()
    finally:
        executor.shutdown()
        spin_thread.join(timeout=2.0)
        for node in (adapter, client_node):
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_nav2_result_future_exception_aborts_and_attempts_safe_stop():
    result_future = ImmediateFuture(
        error=RuntimeError('Nav2 result transport lost')
    )
    nav_handle = FakeAcceptedNav2Goal(result_future)
    adapter, goal_handle = make_unit_adapter(nav_handle)

    result = adapter._execute(goal_handle)

    assert result.outcome == NavigateToNamedLocation.Result.OUTCOME_FAILED
    assert result.message
    assert 'Nav2 result transport lost' in result.message
    assert 'safe Nav2 stop could not be confirmed' in result.message
    assert nav_handle.cancel_calls == 1
    assert nav_handle.command_active is False
    goal_handle.abort.assert_called_once_with()
    goal_handle.succeed.assert_not_called()
    goal_handle.canceled.assert_not_called()
    assert adapter._goal_reserved is False
    assert adapter.shutdown_complete()


def test_missing_nav2_result_future_still_attempts_cancel():
    nav_handle = FakeAcceptedNav2Goal(ImmediateFuture())
    nav_handle.get_result_async = Mock(
        side_effect=RuntimeError('cannot request Nav2 result')
    )
    adapter, goal_handle = make_unit_adapter(nav_handle)

    result = adapter._execute(goal_handle)

    assert result.outcome == NavigateToNamedLocation.Result.OUTCOME_FAILED
    assert 'cannot request Nav2 result' in result.message
    assert 'safe Nav2 stop could not be confirmed' in result.message
    assert 'result future is unavailable' in result.message
    assert nav_handle.cancel_calls == 1
    assert nav_handle.command_active is False
    goal_handle.abort.assert_called_once_with()
    assert adapter._goal_reserved is False
    assert adapter.shutdown_complete()


def test_cancel_future_exception_aborts_without_claiming_safe_stop():
    result_future = ImmediateFuture(
        error=RuntimeError('Nav2 result transport lost')
    )
    nav_handle = FakeAcceptedNav2Goal(
        result_future,
        cancel_error=RuntimeError('cancel transport lost'),
    )
    adapter, goal_handle = make_unit_adapter(nav_handle)

    result = adapter._execute(goal_handle)

    assert result.outcome == NavigateToNamedLocation.Result.OUTCOME_FAILED
    assert 'safe Nav2 stop could not be confirmed' in result.message
    assert 'cancel transport lost' in result.message
    assert 'cancellation and stopped state confirmed' not in result.message
    assert nav_handle.cancel_calls == 1
    assert nav_handle.command_active is False
    goal_handle.abort.assert_called_once_with()
    goal_handle.canceled.assert_not_called()
    assert adapter._goal_reserved is False
    assert adapter.shutdown_complete()


@pytest.mark.parametrize(
    ('failing_boundary', 'expected_message'),
    [
        ('resolver_call', 'resolver submission failed'),
        ('resolver_future', 'named-location resolution failed'),
        ('nav2_call', 'nav2 submission failed'),
        ('nav2_future', 'nav2 goal submission failed'),
    ],
)
def test_submission_exception_aborts_with_structured_failure(
    failing_boundary,
    expected_message,
):
    nav_handle = FakeAcceptedNav2Goal(
        ImmediateFuture(
            SimpleNamespace(
                status=GoalStatus.STATUS_SUCCEEDED,
                result=NavigateToPose.Result(),
            )
        )
    )
    adapter, goal_handle = make_unit_adapter(nav_handle)
    if failing_boundary == 'resolver_call':
        adapter._resolver.call_async.side_effect = RuntimeError(
            'resolver submission failed'
        )
    elif failing_boundary == 'resolver_future':
        adapter._resolver.call_async.return_value = ImmediateFuture(
            error=RuntimeError('resolver future failed')
        )
    elif failing_boundary == 'nav2_call':
        adapter._nav2.send_goal_async.side_effect = RuntimeError(
            'Nav2 submission failed'
        )
    else:
        adapter._nav2.send_goal_async.return_value = ImmediateFuture(
            error=RuntimeError('Nav2 future failed')
        )

    result = adapter._execute(goal_handle)

    assert result.outcome == NavigateToNamedLocation.Result.OUTCOME_FAILED
    assert expected_message in result.message.lower()
    assert result.message
    assert nav_handle.cancel_calls == 0
    goal_handle.abort.assert_called_once_with()
    goal_handle.succeed.assert_not_called()
    assert adapter._goal_reserved is False
    assert adapter.shutdown_complete()


def test_nav2_aborted_status_cannot_use_default_success_payload():
    wrapped_result = SimpleNamespace(
        status=GoalStatus.STATUS_ABORTED,
        result=NavigateToPose.Result(),
    )
    nav_handle = FakeAcceptedNav2Goal(ImmediateFuture(wrapped_result))
    adapter, goal_handle = make_unit_adapter(nav_handle)

    result = adapter._execute(goal_handle)

    assert result.outcome != NavigateToNamedLocation.Result.OUTCOME_SUCCEEDED
    assert result.outcome == NavigateToNamedLocation.Result.OUTCOME_UNREACHABLE
    assert result.message
    goal_handle.abort.assert_called_once_with()
    goal_handle.succeed.assert_not_called()
    assert nav_handle.cancel_calls == 0
    assert adapter._goal_reserved is False
    assert adapter.shutdown_complete()


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


def test_client_cancel_confirms_nav2_stop_before_reporting_cancelled(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    monkeypatch.setenv('ROS_DOMAIN_ID', '173')
    monkeypatch.setenv('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    rclpy.init()
    adapter = NamedNavigationAdapter()
    dependencies = FakeNavigationDependencies(block_navigation=True)
    client_node = rclpy.create_node('named_navigation_cancel_client')
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

        cancel_response = wait_future(goal_handle.cancel_goal_async())
        assert cancel_response.goals_canceling
        wrapped_result = wait_future(result_future)

        assert wrapped_result.status == GoalStatus.STATUS_CANCELED
        assert wrapped_result.result.outcome == (
            NavigateToNamedLocation.Result.OUTCOME_CANCELLED
        )
        assert 'Nav2 cancellation and stopped state confirmed' in (
            wrapped_result.result.message
        )
        assert dependencies.navigation_cancelled.is_set()
        assert adapter._goal_reserved is False
        assert adapter.shutdown_complete()
    finally:
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
