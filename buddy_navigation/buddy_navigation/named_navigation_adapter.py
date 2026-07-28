"""Adapt Buddy named navigation goals to Nav2 NavigateToPose."""

import asyncio
import math
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
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

from .cancellation import confirm_downstream_cancel
from .navigation_core import check_preconditions, nav2_terminal_outcome, Outcome


ACTION_NAME = '/buddy/navigation/navigate_to_named_location'
RESOLVE_SERVICE = '/buddy/world/resolve_named_location'
NAV2_ACTION = '/navigate_to_pose'
SAFETY_TOPIC = '/buddy/safety/state'
DIAGNOSTICS_TOPIC = '/diagnostics'


class NamedNavigationAdapter(Node):
    """Resolve semantic names, enforce preconditions, and delegate to Nav2."""

    def __init__(self) -> None:
        super().__init__('named_navigation_adapter', namespace='/buddy')
        self.declare_parameter('navigation_timeout_sec', 300.0)
        self.declare_parameter('dependency_timeout_sec', 2.0)
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')

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
        self._publish_diagnostic(DiagnosticStatus.OK, 'ready', 'adapter is ready')

    def _on_safety(self, message: SafetyState) -> None:
        self._safety = message

    def _accept_goal(self, goal_request) -> GoalResponse:
        if not goal_request.location_name.strip():
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _accept_cancel(self, _goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

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

    async def _execute(self, goal_handle):
        self._latest_pose = None
        self._send_feedback(
            goal_handle,
            NavigateToNamedLocation.Feedback.STATE_RESOLVING,
            'resolving named location',
        )
        timeout = float(self.get_parameter('dependency_timeout_sec').value)
        if not self._resolver.wait_for_service(timeout_sec=timeout):
            return self._finish(
                goal_handle, Outcome.FAILED, 'named-location resolver is unavailable'
            )

        request = ResolveNamedLocation.Request()
        request.name = goal_handle.request.location_name.strip()
        try:
            response = await asyncio.wait_for(
                self._resolver.call_async(request), timeout=timeout
            )
        except (asyncio.TimeoutError, Exception) as error:
            self.get_logger().error(f'named-location resolution failed: {error}')
            return self._finish(
                goal_handle, Outcome.FAILED, 'named-location resolution timed out'
            )

        decision = check_preconditions(
            location_found=response.found and response.location.enabled,
            localization_available=self._localization_available(),
            safety_state_received=self._safety is not None,
            motion_permitted=self._motion_permitted(),
        )
        if decision is not None:
            return self._finish(goal_handle, decision.outcome, decision.message)
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
        nav_handle = await self._nav2.send_goal_async(
            nav_goal,
            feedback_callback=lambda feedback: self._forward_feedback(
                goal_handle, feedback.feedback
            ),
        )
        if not nav_handle.accepted:
            return self._finish(
                goal_handle, Outcome.UNREACHABLE, 'Nav2 rejected the destination'
            )

        result_future = nav_handle.get_result_async()
        started = time.monotonic()
        navigation_timeout = float(self.get_parameter('navigation_timeout_sec').value)
        while not result_future.done():
            if goal_handle.is_cancel_requested:
                return await self._stop_delegated_goal(
                    goal_handle,
                    nav_handle,
                    result_future,
                    Outcome.CANCELLED,
                    'navigation cancelled by client',
                )
            if not self._motion_permitted():
                return await self._stop_delegated_goal(
                    goal_handle,
                    nav_handle,
                    result_future,
                    Outcome.SAFETY_STOP,
                    'navigation stopped by safety state',
                )
            if time.monotonic() - started >= navigation_timeout:
                return await self._stop_delegated_goal(
                    goal_handle,
                    nav_handle,
                    result_future,
                    Outcome.FAILED,
                    'navigation timed out; Nav2 stopped',
                )
            await asyncio.sleep(0.05)

        wrapped_result = result_future.result()
        decision = nav2_terminal_outcome(
            wrapped_result.status,
            succeeded_status=GoalStatus.STATUS_SUCCEEDED,
            canceled_status=GoalStatus.STATUS_CANCELED,
        )
        return self._finish(goal_handle, decision.outcome, decision.message)

    async def _stop_delegated_goal(
        self,
        goal_handle,
        nav_handle,
        result_future,
        outcome: Outcome,
        message: str,
    ):
        confirmation = await confirm_downstream_cancel(
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
                f'cannot confirm safe Nav2 stop: {confirmation.message}',
            )
        return self._finish(
            goal_handle,
            outcome,
            f'{message}; {confirmation.message}',
        )

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


def main(args=None) -> None:
    rclpy.init(args=args)
    node = NamedNavigationAdapter()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
