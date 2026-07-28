"""Bounded ROS action execution through only frozen capability interfaces."""

import threading
import time
import uuid

from buddy_capabilities.catalog import (
    ERROR_CAPABILITY_UNAVAILABLE, ERROR_PRECONDITION, ERROR_TIMEOUT, schema_for,
    validate_arguments)
from buddy_interfaces.action import ExecuteTask, NavigateToNamedLocation, Speak
from buddy_interfaces.msg import RobotStatus, SafetyState, TaskStepResult, WorldSummary
from buddy_task_executor.validation import duration_seconds, validate_static_plan
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class TaskExecutive(Node):
    """Validate plans first, then execute their registered capabilities in order."""

    def __init__(self):
        super().__init__('task_executive', namespace='/buddy')
        # ROS 2 declares use_sim_time automatically; accepting that standard
        # parameter keeps this node simulation-time compatible.
        self.declare_parameter('max_step_timeout_seconds', 120.0)
        self.declare_parameter('max_overall_timeout_seconds', 300.0)
        self.declare_parameter('navigation_recovery_attempts', 1)
        self.declare_parameter('cancellation_wait_seconds', 2.0)
        self._lock = threading.Lock()
        self._callback_group = ReentrantCallbackGroup()
        self._status = None
        self._world = None
        self._active_lower_goal = None
        self._active_goal = None
        self._active_cancel_event = None
        state_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                               durability=DurabilityPolicy.TRANSIENT_LOCAL)
        diagnostics_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                                     durability=DurabilityPolicy.VOLATILE)
        self._status_subscription = self.create_subscription(
            RobotStatus, '/buddy/status', self._status_callback, state_qos)
        self._world_subscription = self.create_subscription(
            WorldSummary, '/buddy/world/summary', self._world_callback, state_qos)
        self._speak_client = ActionClient(
            self, Speak, '/buddy/voice/speak', callback_group=self._callback_group)
        self._navigate_client = ActionClient(
            self, NavigateToNamedLocation,
            '/buddy/navigation/navigate_to_named_location', callback_group=self._callback_group)
        self._server = ActionServer(
            self, ExecuteTask, '/buddy/tasks/execute', self._execute,
            goal_callback=self._goal_callback, cancel_callback=self._cancel_callback,
            callback_group=self._callback_group)
        self._diagnostics = self.create_publisher(DiagnosticArray, '/diagnostics', diagnostics_qos)
        self._timer = self.create_timer(1.0, self._publish_diagnostics)

    def _status_callback(self, message: RobotStatus) -> None:
        with self._lock:
            self._status = message

    def _world_callback(self, message: WorldSummary) -> None:
        with self._lock:
            self._world = message

    def _goal_callback(self, _goal_request):
        # Accept to return a structured ExecuteTask.Result after full validation.
        # This still never permits a side effect before validation completes.
        return GoalResponse.ACCEPT

    @staticmethod
    def _cancel_callback(_goal_handle):
        return CancelResponse.ACCEPT

    def _validate_runtime(self, plan):
        static_failure = validate_static_plan(
            plan,
            self.get_parameter('max_step_timeout_seconds').value,
            self.get_parameter('max_overall_timeout_seconds').value)
        if static_failure:
            return static_failure
        for index, step in enumerate(plan.steps):
            schema = schema_for(step.capability)
            available, reason = self._available(schema.name)
            if not available:
                return _failure(ERROR_CAPABILITY_UNAVAILABLE, reason, index)
            arguments = validate_arguments(schema, step.arguments)
            precondition = self._precondition(schema.name, arguments)
            if precondition:
                return _failure(ERROR_PRECONDITION, precondition, index)
        return None

    def _available(self, capability: str) -> tuple[bool, str]:
        if capability == 'stop':
            return True, ''
        if capability == 'speak':
            return self._speak_client.server_is_ready(), 'speech action unavailable'
        if capability == 'navigate_to':
            return self._navigate_client.server_is_ready(), 'navigation action unavailable'
        with self._lock:
            status = self._status
        return status is not None, 'robot status unavailable'

    def _precondition(self, capability: str, arguments: dict[str, str]) -> str:
        if capability == 'stop' or capability == 'speak':
            return ''
        with self._lock:
            status = self._status
            world = self._world
        if capability == 'report_status':
            return '' if status is not None else 'robot status unavailable'
        if status is None or world is None:
            return 'robot status or world summary unavailable'
        if not any(location.enabled and location.name == arguments['location']
                   for location in world.named_locations):
            return 'named location is unavailable'
        if status.localization_state != RobotStatus.LOCALIZATION_GOOD:
            return 'localization is not good'
        if not status.motion_ready or not status.safety.motion_permitted:
            return 'safety does not permit motion'
        allowed_states = (SafetyState.STATE_NORMAL, SafetyState.STATE_LIMITED)
        if status.safety.state not in allowed_states or status.safety.emergency_stop_latched:
            return 'safety state prohibits motion'
        return ''

    def _execute(self, goal_handle):
        plan = goal_handle.request.plan
        result = ExecuteTask.Result()
        self._feedback(goal_handle, ExecuteTask.Feedback.STATE_VALIDATING, 0, len(plan.steps),
                       '', 'validating task plan')
        failure = self._validate_runtime(plan)
        if failure:
            result.outcome = ExecuteTask.Result.OUTCOME_REJECTED
            result.message = failure.message
            if failure.step_index is not None:
                result.step_results = [self._step_result(
                    plan.steps[failure.step_index], TaskStepResult.OUTCOME_REJECTED,
                    failure.code, failure.message)]
            goal_handle.abort()
            return result

        owns_active_task = False
        with self._lock:
            if self._active_goal is not None and not self._is_stop_only(plan):
                result.outcome = ExecuteTask.Result.OUTCOME_REJECTED
                result.message = 'another task is active'
                goal_handle.abort()
                return result
            if self._active_goal is None:
                self._active_goal = goal_handle
                self._active_cancel_event = threading.Event()
                owns_active_task = True
        if not owns_active_task:
            self._request_soft_stop()
            stop = plan.steps[0]
            result.outcome = ExecuteTask.Result.OUTCOME_SUCCEEDED
            result.step_results = [self._step_result(
                stop, TaskStepResult.OUTCOME_SUCCEEDED, 0,
                'active task cancellation requested')]
            result.message = 'active task cancellation requested'
            goal_handle.succeed()
            return result
        deadline = time.monotonic() + self.get_parameter('max_overall_timeout_seconds').value
        step_results = []
        had_failure = False
        try:
            for index, step in enumerate(plan.steps):
                if self._should_cancel(goal_handle):
                    self._cancel_lower_and_wait()
                    result.outcome = ExecuteTask.Result.OUTCOME_CANCELLED
                    result.message = 'task cancellation requested'
                    if goal_handle.is_cancel_requested:
                        goal_handle.canceled()
                    else:
                        goal_handle.abort()
                    break
                if time.monotonic() >= deadline:
                    step_results.append(self._step_result(
                        step, TaskStepResult.OUTCOME_TIMED_OUT, ERROR_TIMEOUT,
                        'overall task timeout exceeded'))
                    result.outcome = ExecuteTask.Result.OUTCOME_FAILED
                    result.message = 'overall task timeout exceeded'
                    goal_handle.abort()
                    break
                self._feedback(goal_handle, ExecuteTask.Feedback.STATE_EXECUTING, index,
                               len(plan.steps), step.capability, 'executing capability')
                step_deadline = min(deadline, time.monotonic() + duration_seconds(step.timeout))
                step_result = self._run_step(
                    goal_handle, step, index, len(plan.steps), step_deadline)
                step_results.append(step_result)
                if step_result.outcome == TaskStepResult.OUTCOME_CANCELLED:
                    result.outcome = ExecuteTask.Result.OUTCOME_CANCELLED
                    result.message = step_result.message
                    if goal_handle.is_cancel_requested:
                        goal_handle.canceled()
                    else:
                        goal_handle.abort()
                    break
                if step_result.outcome != TaskStepResult.OUTCOME_SUCCEEDED:
                    had_failure = True
                    if step.on_failure == 0:
                        result.outcome = ExecuteTask.Result.OUTCOME_FAILED
                        result.message = step_result.message
                        goal_handle.abort()
                        break
            else:
                result.outcome = (ExecuteTask.Result.OUTCOME_PARTIALLY_SUCCEEDED if had_failure
                                  else ExecuteTask.Result.OUTCOME_SUCCEEDED)
                result.message = (
                    'task completed' if not had_failure else 'task completed with failures')
                goal_handle.succeed()
        finally:
            with self._lock:
                if owns_active_task:
                    self._active_goal = None
                    self._active_lower_goal = None
                    self._active_cancel_event = None
        result.step_results = step_results
        return result

    def _run_step(self, goal_handle, step, index, total, deadline):
        schema = schema_for(step.capability)
        arguments = validate_arguments(schema, step.arguments)
        if schema.name == 'stop':
            self._request_soft_stop()
            return self._step_result(step, TaskStepResult.OUTCOME_SUCCEEDED, 0,
                                     'active motion cancellation requested')
        if schema.name == 'report_status':
            with self._lock:
                status = self._status
            message = 'mode={} battery_known={}'.format(status.mode, status.battery_state_known)
            return self._step_result(step, TaskStepResult.OUTCOME_SUCCEEDED, 0, message)
        if schema.name == 'speak':
            return self._run_speak(goal_handle, step, arguments, deadline)
        return self._run_navigation(goal_handle, step, arguments, index, total, deadline)

    def _run_speak(self, goal_handle, step, arguments, deadline):
        request = Speak.Goal()
        request.request_id.uuid = list(uuid.uuid4().bytes)
        request.text = arguments['text']
        request.voice = arguments.get('voice', '')
        request.priority = 0
        request.interrupt_current = False
        goal = self._wait(self._speak_client.send_goal_async(request), deadline, goal_handle)
        if goal is None:
            if self._should_cancel(goal_handle):
                return self._step_result(step, TaskStepResult.OUTCOME_CANCELLED, 0,
                                         'speech cancelled')
            return self._step_result(step, TaskStepResult.OUTCOME_TIMED_OUT, ERROR_TIMEOUT,
                                     'speech action timed out')
        if not goal.accepted:
            return self._step_result(step, TaskStepResult.OUTCOME_REJECTED,
                                     ERROR_CAPABILITY_UNAVAILABLE, 'speech goal rejected')
        with self._lock:
            self._active_lower_goal = goal
        action_result = self._wait(goal.get_result_async(), deadline, goal_handle, goal)
        with self._lock:
            self._active_lower_goal = None
        if action_result is None:
            if self._should_cancel(goal_handle):
                return self._step_result(step, TaskStepResult.OUTCOME_CANCELLED, 0,
                                         'speech cancelled')
            return self._step_result(step, TaskStepResult.OUTCOME_TIMED_OUT, ERROR_TIMEOUT,
                                     'speech action timed out')
        if action_result.result.outcome == Speak.Result.OUTCOME_SUCCEEDED:
            return self._step_result(
                step, TaskStepResult.OUTCOME_SUCCEEDED, 0, action_result.result.message)
        outcome = (TaskStepResult.OUTCOME_CANCELLED if self._should_cancel(goal_handle)
                   else TaskStepResult.OUTCOME_FAILED)
        return self._step_result(step, outcome, ERROR_CAPABILITY_UNAVAILABLE,
                                 action_result.result.message)

    def _run_navigation(self, goal_handle, step, arguments, index, total, deadline):
        attempts = 1 + self.get_parameter('navigation_recovery_attempts').value
        last = None
        for attempt in range(attempts):
            if attempt:
                self._feedback(goal_handle, ExecuteTask.Feedback.STATE_RECOVERING, index, total,
                               step.capability, 'bounded navigation recovery')
            request = NavigateToNamedLocation.Goal()
            request.location_name = arguments['location']
            goal = self._wait(
                self._navigate_client.send_goal_async(request), deadline, goal_handle)
            if goal is None:
                if self._should_cancel(goal_handle):
                    return self._step_result(step, TaskStepResult.OUTCOME_CANCELLED, 0,
                                             'navigation cancelled')
                return self._step_result(step, TaskStepResult.OUTCOME_TIMED_OUT, ERROR_TIMEOUT,
                                         'navigation action timed out')
            if not goal.accepted:
                return self._step_result(step, TaskStepResult.OUTCOME_REJECTED,
                                         ERROR_CAPABILITY_UNAVAILABLE, 'navigation goal rejected')
            with self._lock:
                self._active_lower_goal = goal
            action_result = self._wait(goal.get_result_async(), deadline, goal_handle, goal)
            with self._lock:
                self._active_lower_goal = None
            if action_result is None:
                if self._should_cancel(goal_handle):
                    return self._step_result(step, TaskStepResult.OUTCOME_CANCELLED, 0,
                                             'navigation cancelled')
                return self._step_result(step, TaskStepResult.OUTCOME_TIMED_OUT, ERROR_TIMEOUT,
                                         'navigation action timed out')
            nav_result = action_result.result
            if nav_result.outcome == NavigateToNamedLocation.Result.OUTCOME_SUCCEEDED:
                return self._step_result(
                    step, TaskStepResult.OUTCOME_SUCCEEDED, 0, nav_result.message)
            if nav_result.outcome == NavigateToNamedLocation.Result.OUTCOME_CANCELLED:
                return self._step_result(
                    step, TaskStepResult.OUTCOME_CANCELLED, 0, nav_result.message)
            last = nav_result.message or 'navigation failed'
            if nav_result.outcome in (
                    NavigateToNamedLocation.Result.OUTCOME_SAFETY_STOP,
                    NavigateToNamedLocation.Result.OUTCOME_UNKNOWN_LOCATION,
                    NavigateToNamedLocation.Result.OUTCOME_LOCALIZATION_UNAVAILABLE):
                break
            if time.monotonic() >= deadline:
                break
        return self._step_result(step, TaskStepResult.OUTCOME_FAILED, ERROR_PRECONDITION, last)

    def _wait(self, future, deadline, goal_handle, action_goal=None):
        while not future.done() and time.monotonic() < deadline:
            if self._should_cancel(goal_handle):
                if action_goal is not None:
                    self._cancel_lower_action(action_goal, future)
                return None
            time.sleep(0.01)
        if not future.done():
            if action_goal is not None:
                self._cancel_lower_action(action_goal, future)
            return None
        return future.result()

    def _request_soft_stop(self) -> None:
        with self._lock:
            event = self._active_cancel_event
        if event is not None:
            event.set()
        self._cancel_lower_and_wait()

    def _cancel_lower_and_wait(self) -> None:
        with self._lock:
            goal = self._active_lower_goal
        if goal is not None:
            self._cancel_lower_action(goal, goal.get_result_async())

    def _cancel_lower_action(self, goal, result_future) -> None:
        deadline = time.monotonic() + self.get_parameter('cancellation_wait_seconds').value
        cancellation = goal.cancel_goal_async()
        while not cancellation.done() and time.monotonic() < deadline:
            time.sleep(0.01)
        while not result_future.done() and time.monotonic() < deadline:
            time.sleep(0.01)

    def _should_cancel(self, goal_handle) -> bool:
        with self._lock:
            event = self._active_cancel_event
        return goal_handle.is_cancel_requested or (event is not None and event.is_set())

    @staticmethod
    def _is_stop_only(plan) -> bool:
        return len(plan.steps) == 1 and plan.steps[0].capability == 'stop'

    def _step_result(self, step, outcome, error_code, message):
        result = TaskStepResult()
        result.step_id = step.step_id
        result.capability = step.capability
        result.outcome = outcome
        result.error_code = error_code
        result.message = message
        return result

    def _feedback(self, goal_handle, state, index, total, capability, message):
        feedback = ExecuteTask.Feedback()
        feedback.state = state
        feedback.current_step_index = index
        feedback.total_steps = total
        feedback.progress = float(index) / float(total) if total else 0.0
        feedback.current_capability = capability
        feedback.message = message
        goal_handle.publish_feedback(feedback)

    def _publish_diagnostics(self) -> None:
        with self._lock:
            active = self._active_goal is not None
        status = DiagnosticStatus()
        status.name = 'buddy_task_executive'
        status.hardware_id = 'buddy'
        status.level = DiagnosticStatus.OK
        status.message = 'task executive active'
        status.values = [KeyValue(key='active_task', value=str(active).lower())]
        message = DiagnosticArray()
        message.header.stamp = self.get_clock().now().to_msg()
        message.status = [status]
        self._diagnostics.publish(message)


def _failure(code, message, step_index):
    from buddy_task_executor.validation import ValidationFailure
    return ValidationFailure(code, message, step_index)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TaskExecutive()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
