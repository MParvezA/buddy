"""Adapt Buddy named navigation goals to Nav2 NavigateToPose."""

import math
import threading
import time

from action_msgs.msg import GoalStatus
from buddy_interfaces.action import NavigateToNamedLocation
from buddy_interfaces.msg import SafetyState
from buddy_interfaces.srv import ResolveNamedLocation
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from nav2_msgs.action import NavigateToPose
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

from .action_execution import execute_with_failure_result
from .cancellation import confirm_downstream_cancel
from .executor_teardown import drain_and_stop_workers
from .navigation_core import check_preconditions, nav2_terminal_outcome, Outcome


ACTION_NAME = '/buddy/navigation/navigate_to_named_location'
RESOLVE_SERVICE = '/buddy/world/resolve_named_location'
NAV2_ACTION = '/navigate_to_pose'
SAFETY_TOPIC = '/buddy/safety/state'
DIAGNOSTICS_TOPIC = '/diagnostics'
LAUNCH_SIGINT_GRACE_SEC = 5.0
ACTIVE_SHUTDOWN_TIMEOUT_SEC = 4.0
EXECUTOR_DRAIN_TIMEOUT_SEC = 0.25
WORKER_JOIN_TIMEOUT_SEC = 0.25
OWNER_STATUS_HEARTBEAT_PERIOD_SEC = 0.05


class DrainingMultiThreadedExecutor(MultiThreadedExecutor):
    """
    Jazzy multi-threaded executor with an explicit callback drain.

    Jazzy has no public API for awaiting the rclpy Tasks submitted to its
    thread pool. Its ``_futures`` list is the version-scoped registry used by
    ``_spin_once_impl`` itself, and the spin thread is stopped before this
    method is called.
    """

    @staticmethod
    def _entity_description(entity) -> str:
        description = f'{type(entity).__module__}.{type(entity).__name__}'
        topic = getattr(entity, 'topic', None)
        if topic:
            description += f'({topic})'
        return description

    def drain_submitted_callbacks(self, timeout_sec: float) -> tuple[str, ...]:
        """Cancel queued Tasks, then await and retrieve running Task outcomes."""
        deadline = time.monotonic() + timeout_sec
        cancelled_sources = []
        first_error = None
        while True:
            with self._tasks_lock:
                tasks = list(self._pending_tasks)
                for future in self._ready_tasks:
                    if future not in tasks:
                        tasks.append(future)
                for future in self._futures:
                    if future not in tasks:
                        tasks.append(future)
            if not tasks:
                return tuple(cancelled_sources)
            made_progress = False
            for future in tasks:
                if future.cancelled():
                    self._release_task(future)
                    made_progress = True
                    continue
                if not future.done():
                    if future.executing():
                        continue
                    with self._tasks_lock:
                        task_data = self._pending_tasks.get(future)
                    source = None if task_data is None else task_data.source_entity
                    cancelled_sources.append(self._entity_description(source))
                    future.cancel()
                    if future.cancelled():
                        self._release_task(future)
                        made_progress = True
                    continue
                error = future.exception()
                self._release_task(future)
                if error is not None:
                    if first_error is None:
                        first_error = error
                else:
                    future.result()
                made_progress = True
            with self._tasks_lock:
                registries_empty = (
                    not self._futures
                    and not self._pending_tasks
                    and not self._ready_tasks
                )
            if registries_empty:
                if first_error is not None:
                    raise first_error
                return tuple(cancelled_sources)
            if time.monotonic() >= deadline:
                pending = []
                with self._tasks_lock:
                    for future in self._pending_tasks:
                        task_data = self._pending_tasks.get(future)
                        source = None if task_data is None else task_data.source_entity
                        pending.append(
                            f'{self._entity_description(source)}'
                            f'(executing={future.executing()})'
                        )
                raise TimeoutError(
                    'executor callbacks did not finish before shutdown: '
                    + ', '.join(pending)
                )
            if not made_progress:
                time.sleep(0.01)

    def _release_task(self, future) -> None:
        with self._tasks_lock:
            self._futures[:] = [
                task for task in self._futures if task is not future
            ]
            self._pending_tasks.pop(future, None)
            self._ready_tasks = type(self._ready_tasks)(
                task for task in self._ready_tasks if task is not future
            )

    def shutdown_workers(self, timeout_sec: float) -> None:
        """Bound joining the private Jazzy ThreadPoolExecutor workers."""
        self._executor.shutdown(wait=False, cancel_futures=True)
        deadline = time.monotonic() + timeout_sec
        for thread in list(self._executor._threads):
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(timeout=remaining)
        alive = [
            thread.name
            for thread in self._executor._threads
            if thread.is_alive()
        ]
        if alive:
            raise TimeoutError(
                'executor worker threads did not stop: ' + ', '.join(alive)
            )


class NamedNavigationAdapter(Node):
    """Resolve semantic names, enforce preconditions, and delegate to Nav2."""

    def __init__(self, *, parameter_overrides=None) -> None:
        super().__init__(
            'named_navigation_adapter',
            namespace='/buddy',
            parameter_overrides=parameter_overrides,
        )
        self.declare_parameter('navigation_timeout_sec', 300.0)
        self.declare_parameter('dependency_timeout_sec', 2.0)
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter(
            'owner_status_heartbeat_period_sec',
            OWNER_STATUS_HEARTBEAT_PERIOD_SEC,
        )
        owner_heartbeat_period_sec = float(
            self.get_parameter('owner_status_heartbeat_period_sec').value
        )
        if (
            not math.isfinite(owner_heartbeat_period_sec)
            or owner_heartbeat_period_sec <= 0.0
        ):
            raise ValueError(
                'owner_status_heartbeat_period_sec '
                'must be finite and positive'
            )

        self._shutdown_requested = threading.Event()
        self._execution_idle = threading.Event()
        self._execution_idle.set()
        self._goal_lock = threading.Lock()
        self._goal_reserved = False
        self._owned_entity_lock = threading.Lock()
        self._action_destroyed = False
        self._nav2_destroyed = False
        self._delegated_goal_lock = threading.Lock()
        self._delegated_nav_handle = None
        self._delegated_result_future = None
        self._delegated_cancel_timeout = 2.0
        self._group = ReentrantCallbackGroup()
        self._resolver = self.create_client(
            ResolveNamedLocation, RESOLVE_SERVICE, callback_group=self._group
        )
        self._nav2 = ActionClient(
            self, NavigateToPose, NAV2_ACTION, callback_group=self._group
        )
        safety_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._safety = None
        self.create_subscription(
            SafetyState, SAFETY_TOPIC, self._on_safety, safety_qos,
            callback_group=self._group,
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
        self._tf_buffer = Buffer(node=self)
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self._latest_pose = None
        self._action = ActionServer(
            self,
            NavigateToNamedLocation,
            ACTION_NAME,
            execute_callback=self._execute,
            goal_callback=self._accept_goal,
            cancel_callback=self._accept_cancel,
            callback_group=self._group,
        )
        self._owner_status_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self._owner_status_timer = self.create_timer(
            owner_heartbeat_period_sec,
            self._publish_owner_status_heartbeat,
            callback_group=self._group,
            clock=self._owner_status_clock,
        )
        self._publish_diagnostic(DiagnosticStatus.OK, 'ready', 'adapter is ready')

    def _on_safety(self, message: SafetyState) -> None:
        self._safety = message

    def _accept_goal(self, goal_request) -> GoalResponse:
        with self._goal_lock:
            if (
                self._shutdown_requested.is_set()
                or self._goal_reserved
                or not goal_request.location_name.strip()
            ):
                return GoalResponse.REJECT
            self._goal_reserved = True
            self._execution_idle.clear()
            return GoalResponse.ACCEPT

    def _accept_cancel(self, _goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    def _publish_owner_status_heartbeat(self) -> None:
        with self._goal_lock:
            goal_reserved = self._goal_reserved
        if not goal_reserved:
            return
        with self._owned_entity_lock:
            if not self._action_destroyed:
                # Jazzy exposes status publication through the action handle.
                self._action._handle.publish_status()

    def _motion_permitted(self) -> bool:
        return bool(
            self._safety is not None
            and self._safety.motion_permitted
            and self._safety.state in (
                SafetyState.STATE_NORMAL,
                SafetyState.STATE_LIMITED,
            )
        )

    def _localization_available(self) -> bool:
        return self._tf_buffer.can_transform(
            self.get_parameter('map_frame').value,
            self.get_parameter('base_frame').value,
            Time(),
            timeout=Duration(seconds=0.05),
        )

    def _execute(self, goal_handle):
        try:
            return execute_with_failure_result(
                self,
                goal_handle,
                self._execute_goal,
            )
        finally:
            self._clear_delegated_goal()
            with self._goal_lock:
                self._goal_reserved = False
                self._execution_idle.set()

    def _execute_goal(self, goal_handle):
        self._latest_pose = None
        self._send_feedback(
            goal_handle,
            NavigateToNamedLocation.Feedback.STATE_RESOLVING,
            'resolving named location',
        )
        timeout = float(self.get_parameter('dependency_timeout_sec').value)
        with self._delegated_goal_lock:
            self._delegated_cancel_timeout = timeout
        if not self._resolver.wait_for_service(timeout_sec=timeout):
            return self._finish(
                goal_handle, Outcome.FAILED, 'named-location resolver is unavailable'
            )

        request = ResolveNamedLocation.Request()
        request.name = goal_handle.request.location_name.strip()
        resolve_future = self._resolver.call_async(request)
        if not self._wait_future(resolve_future, timeout):
            return self._finish(
                goal_handle, Outcome.FAILED, 'named-location resolution timed out'
            )
        resolve_error = resolve_future.exception()
        if resolve_error is not None:
            self.get_logger().error(
                f'named-location resolution failed: {resolve_error}'
            )
            return self._finish(
                goal_handle, Outcome.FAILED, 'named-location resolution failed'
            )
        response = resolve_future.result()

        decision = check_preconditions(
            location_found=response.found and response.location.enabled,
            localization_available=self._localization_available(),
            safety_state_received=self._safety is not None,
            motion_permitted=self._motion_permitted(),
        )
        if decision is not None:
            return self._finish(goal_handle, decision.outcome, decision.message)
        if self._shutdown_requested.is_set():
            return self._finish(
                goal_handle,
                Outcome.FAILED,
                'navigation stopped for adapter shutdown before planning',
            )
        if goal_handle.is_cancel_requested:
            return self._finish(goal_handle, Outcome.CANCELLED, 'cancelled before planning')
        if not self._nav2.wait_for_server(timeout_sec=timeout):
            return self._finish(goal_handle, Outcome.FAILED, 'Nav2 is unavailable')

        self._send_feedback(
            goal_handle,
            NavigateToNamedLocation.Feedback.STATE_PLANNING,
            'submitting pose to Nav2',
        )
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose = response.location.pose
        nav_goal.behavior_tree = ''
        nav_goal_future = self._nav2.send_goal_async(
            nav_goal,
            feedback_callback=lambda feedback: self._forward_feedback(
                goal_handle, feedback.feedback
            ),
        )
        if not self._wait_future(nav_goal_future, timeout):
            return self._finish(
                goal_handle, Outcome.FAILED, 'Nav2 goal submission timed out'
            )
        nav_goal_error = nav_goal_future.exception()
        if nav_goal_error is not None:
            self.get_logger().error(f'Nav2 goal submission failed: {nav_goal_error}')
            return self._finish(
                goal_handle, Outcome.FAILED, 'Nav2 goal submission failed'
            )
        nav_handle = nav_goal_future.result()
        self._track_delegated_goal(nav_handle, None)
        if not nav_handle.accepted:
            return self._finish(
                goal_handle, Outcome.UNREACHABLE, 'Nav2 rejected the destination'
            )

        result_future = nav_handle.get_result_async()
        self._track_delegated_goal(nav_handle, result_future)
        if self._shutdown_requested.is_set():
            return self._stop_delegated_goal(
                goal_handle,
                nav_handle,
                result_future,
                Outcome.FAILED,
                'navigation stopped for adapter shutdown',
            )
        started = time.monotonic()
        navigation_timeout = float(self.get_parameter('navigation_timeout_sec').value)
        while not result_future.done():
            if self._shutdown_requested.is_set():
                return self._stop_delegated_goal(
                    goal_handle,
                    nav_handle,
                    result_future,
                    Outcome.FAILED,
                    'navigation stopped for adapter shutdown',
                )
            if goal_handle.is_cancel_requested:
                return self._stop_delegated_goal(
                    goal_handle,
                    nav_handle,
                    result_future,
                    Outcome.CANCELLED,
                    'navigation cancelled by client',
                )
            if not self._motion_permitted():
                return self._stop_delegated_goal(
                    goal_handle,
                    nav_handle,
                    result_future,
                    Outcome.SAFETY_STOP,
                    'navigation stopped by safety state',
                )
            if time.monotonic() - started >= navigation_timeout:
                return self._stop_delegated_goal(
                    goal_handle,
                    nav_handle,
                    result_future,
                    Outcome.FAILED,
                    'navigation timed out; Nav2 stopped',
                )
            time.sleep(0.05)

        result_error = result_future.exception()
        if result_error is not None:
            raise RuntimeError(f'Nav2 result failed: {result_error}')
        wrapped_result = result_future.result()
        decision = nav2_terminal_outcome(
            wrapped_result.status,
            succeeded_status=GoalStatus.STATUS_SUCCEEDED,
            canceled_status=GoalStatus.STATUS_CANCELED,
        )
        return self._finish(goal_handle, decision.outcome, decision.message)

    def _stop_delegated_goal(
        self,
        goal_handle,
        nav_handle,
        result_future,
        outcome: Outcome,
        message: str,
    ):
        confirmation = confirm_downstream_cancel(
            nav_handle,
            result_future,
            canceled_status=GoalStatus.STATUS_CANCELED,
            timeout_sec=float(self.get_parameter('dependency_timeout_sec').value),
        )
        if not confirmation.confirmed:
            self.get_logger().error(confirmation.message)
            return self._finish(
                goal_handle,
                Outcome.FAILED,
                f'safe Nav2 stop could not be confirmed: {confirmation.message}',
            )
        return self._finish(
            goal_handle,
            outcome,
            f'{message}; {confirmation.message}',
        )

    def _track_delegated_goal(self, nav_handle, result_future) -> None:
        with self._delegated_goal_lock:
            self._delegated_nav_handle = nav_handle
            self._delegated_result_future = result_future

    def _clear_delegated_goal(self) -> None:
        with self._delegated_goal_lock:
            self._delegated_nav_handle = None
            self._delegated_result_future = None

    def _finish_unexpected_failure(self, goal_handle, error: Exception):
        message = (
            f'navigation failed unexpectedly: {type(error).__name__}: {error}'
        )
        with self._delegated_goal_lock:
            nav_handle = self._delegated_nav_handle
            result_future = self._delegated_result_future
            cancel_timeout = self._delegated_cancel_timeout
        if nav_handle is not None:
            confirmation = confirm_downstream_cancel(
                nav_handle,
                result_future,
                canceled_status=GoalStatus.STATUS_CANCELED,
                timeout_sec=cancel_timeout,
            )
            if confirmation.confirmed:
                message += f'; {confirmation.message}'
            else:
                message += (
                    '; safe Nav2 stop could not be confirmed: '
                    f'{confirmation.message}'
                )
        self.get_logger().error(message)
        return self._finish(goal_handle, Outcome.FAILED, message)

    def request_shutdown(self) -> None:
        """Request cancellation while the ROS context can still contact Nav2."""
        with self._goal_lock:
            self._shutdown_requested.set()
            if not self._goal_reserved:
                self._execution_idle.set()

    def shutdown_complete(self) -> bool:
        """Report whether the active Buddy action callback has finished."""
        return self._execution_idle.is_set()

    def shutdown_timeout_seconds(self) -> float:
        """Reserve launch-grace time for executor and ROS entity teardown."""
        dependency_bound = float(
            self.get_parameter('dependency_timeout_sec').value
        )
        return min(
            ACTIVE_SHUTDOWN_TIMEOUT_SEC,
            max(0.1, (2.0 * dependency_bound) + EXECUTOR_DRAIN_TIMEOUT_SEC),
        )

    def destroy_owned_entities(self) -> None:
        """Idempotently destroy action waitables before destroying the node."""
        with self._owned_entity_lock:
            if not self._action_destroyed:
                owner_status_timer = getattr(
                    self,
                    '_owner_status_timer',
                    None,
                )
                if owner_status_timer is not None:
                    owner_status_timer.cancel()
                self._action.destroy()
                self._action_destroyed = True
            if not self._nav2_destroyed:
                self._nav2.destroy()
                self._nav2_destroyed = True

    def destroy_node(self):
        """Destroy action waitables before the node-owned ROS entities."""
        self.destroy_owned_entities()
        return super().destroy_node()

    @staticmethod
    def _wait_future(future, timeout_sec: float) -> bool:
        deadline = time.monotonic() + timeout_sec
        while not future.done():
            if not rclpy.ok() or time.monotonic() >= deadline:
                return False
            time.sleep(0.01)
        return True

    def _forward_feedback(self, goal_handle, nav_feedback) -> None:
        self._latest_pose = nav_feedback.current_pose
        state = NavigateToNamedLocation.Feedback.STATE_MOVING
        if nav_feedback.number_of_recoveries > 0:
            state = NavigateToNamedLocation.Feedback.STATE_RECOVERING
        feedback = NavigateToNamedLocation.Feedback()
        feedback.state = state
        feedback.current_pose = nav_feedback.current_pose
        feedback.distance_remaining = float(nav_feedback.distance_remaining)
        feedback.navigation_time = nav_feedback.navigation_time
        feedback.message = 'Nav2 navigation in progress'
        goal_handle.publish_feedback(feedback)

    def _send_feedback(self, goal_handle, state: int, message: str) -> None:
        feedback = NavigateToNamedLocation.Feedback()
        feedback.state = state
        feedback.distance_remaining = math.nan
        feedback.message = message
        goal_handle.publish_feedback(feedback)

    def _finish(self, goal_handle, outcome: Outcome, message: str):
        result = NavigateToNamedLocation.Result()
        result.outcome = int(outcome)
        result.message = message
        if self._latest_pose is not None:
            result.reached_pose = self._latest_pose
        if outcome == Outcome.SUCCEEDED:
            goal_handle.succeed()
            level = DiagnosticStatus.OK
        elif outcome == Outcome.CANCELLED:
            goal_handle.canceled()
            level = DiagnosticStatus.WARN
        else:
            goal_handle.abort()
            level = DiagnosticStatus.WARN
        self._publish_diagnostic(level, outcome.name.lower(), message)
        return result

    def _publish_diagnostic(self, level: int, state: str, message: str) -> None:
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = 'buddy/navigation/named_navigation_adapter'
        status.hardware_id = 'software'
        status.level = level
        status.message = message
        status.values = [KeyValue(key='state', value=state)]
        array.status = [status]
        self._diagnostics.publish(array)


def _drain_active_navigation(node, executor) -> None:
    node.request_shutdown()
    deadline = time.monotonic() + node.shutdown_timeout_seconds()
    while not node.shutdown_complete() and time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if rclpy.ok():
            executor.spin_once(timeout_sec=min(0.05, remaining))
        else:
            time.sleep(min(0.01, remaining))


def main(args=None) -> None:
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = NamedNavigationAdapter()
    executor = DrainingMultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        _drain_active_navigation(node, executor)
    finally:
        teardown = drain_and_stop_workers(
            executor,
            drain_timeout_sec=min(
                EXECUTOR_DRAIN_TIMEOUT_SEC,
                node.shutdown_timeout_seconds(),
            ),
            worker_timeout_sec=WORKER_JOIN_TIMEOUT_SEC,
        )
        if teardown.cancelled_sources:
            node.get_logger().info(
                'cancelled queued callbacks before shutdown: '
                + ', '.join(teardown.cancelled_sources)
            )
        for error in teardown.errors:
            node.get_logger().error(error)
        try:
            executor.shutdown()
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
        try:
            node.destroy_node()
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
        if rclpy.ok():
            try:
                rclpy.shutdown()
            except (KeyboardInterrupt, ExternalShutdownException):
                pass
