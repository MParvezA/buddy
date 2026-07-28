"""Bounded ROS action execution through only frozen capability interfaces."""

import threading
import time
import uuid

from action_msgs.msg import GoalStatus
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
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions


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
        while self._futures:
            made_progress = False
            for future in self._futures[:]:
                if future.cancelled():
                    self._futures.remove(future)
                    made_progress = True
                    continue
                if not future.done():
                    if future.executing():
                        continue
                    with self._tasks_lock:
                        task_data = self._pending_tasks.get(future)
                    source = None if task_data is None else task_data.source_entity
                    cancelled_sources.append(self._entity_description(source))
                    # A task can transition to executing between the check above
                    # and cancel().  Keep it tracked in that case so a terminal
                    # outcome is still retrieved rather than silently discarded.
                    future.cancel()
                    if future.cancelled():
                        self._futures.remove(future)
                        made_progress = True
                    continue
                self._futures.remove(future)
                error = future.exception()
                if error is not None:
                    raise error
                future.result()
                made_progress = True
            if not self._futures:
                return tuple(cancelled_sources)
            if time.monotonic() >= deadline:
                pending = []
                with self._tasks_lock:
                    for future in self._futures:
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
        return tuple(cancelled_sources)

    def shutdown(self, timeout_sec: float = 0.25) -> bool:
        """Close Jazzy's worker pool within a finite teardown bound.

        ``MultiThreadedExecutor`` inherits ``Executor.shutdown`` in Jazzy.  That
        method stops the ROS wait set but does not shut down its private
        ``ThreadPoolExecutor``.  The remaining non-daemon workers keep an idle
        ``ros2 launch`` process alive after SIGINT.  Callers drain action work
        before this method, so only idle workers should remain here; the bounded
        join is a final check rather than an unbounded second drain.
        """
        super().shutdown(timeout_sec=0.0)
        self._executor.shutdown(wait=False, cancel_futures=True)
        deadline = time.monotonic() + max(0.0, timeout_sec)
        workers = tuple(getattr(self._executor, '_threads', ()))
        for worker in workers:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            worker.join(remaining)
        return all(not worker.is_alive() for worker in workers)


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
        self._active_lower_result = None
        self._pending_lower_submission = None
        # A bounded ExecuteTask result must not make an unconfirmed lower
        # action disappear.  If its cancellation acknowledgement or terminal
        # result cannot be observed within the bound, retain this ownership and
        # admit only the registered stop capability until a terminal result is
        # observed or a later stop retry confirms cancellation.
        self._quarantined_lower_goal = None
        self._quarantined_lower_result = None
        self._quarantined_lower_submission = None
        self._quarantine_reason = ''
        self._active_goal = None
        self._active_cancel_event = None
        self._execution_idle = threading.Event()
        self._execution_idle.set()
        self._owned_actions_destroyed = False
        self._cancellation_failure = ''
        self._lower_cancellation_in_progress = False
        self._lower_cancellation_complete = threading.Event()
        self._lower_cancellation_result = None
        self._shutdown_deadline = None
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
        owns_active_task = False
        plan = None
        current_step = None
        step_results = []
        try:
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

            with self._lock:
                unresolved_lower_action = self._has_quarantined_lower_action_locked()
                if ((self._active_goal is not None or unresolved_lower_action)
                        and not self._is_stop_only(plan)):
                    result.outcome = ExecuteTask.Result.OUTCOME_REJECTED
                    result.message = (
                        'lower action cancellation is unresolved; only registered stop is allowed'
                        if unresolved_lower_action else 'another task is active')
                    goal_handle.abort()
                    return result
                if self._active_goal is None:
                    self._active_goal = goal_handle
                    self._active_cancel_event = threading.Event()
                    self._execution_idle.clear()
                    self._cancellation_failure = ''
                    self._lower_cancellation_in_progress = False
                    self._lower_cancellation_complete.clear()
                    self._lower_cancellation_result = None
                    self._shutdown_deadline = None
                    owns_active_task = True
            if not owns_active_task:
                stopped, message = self._request_soft_stop()
                stop = plan.steps[0]
                outcome = (
                    TaskStepResult.OUTCOME_SUCCEEDED
                    if stopped else TaskStepResult.OUTCOME_FAILED)
                result.outcome = (
                    ExecuteTask.Result.OUTCOME_SUCCEEDED
                    if stopped else ExecuteTask.Result.OUTCOME_FAILED)
                result.step_results = [self._step_result(
                    stop, outcome, 0 if stopped else ERROR_TIMEOUT, message)]
                result.message = message
                if stopped:
                    goal_handle.succeed()
                else:
                    goal_handle.abort()
                return result

            deadline = time.monotonic() + self.get_parameter(
                'max_overall_timeout_seconds').value
            had_failure = False
            for index, step in enumerate(plan.steps):
                current_step = step
                if self._should_cancel(goal_handle):
                    stopped, message = self._cancel_lower_and_wait()
                    if stopped:
                        result.outcome = ExecuteTask.Result.OUTCOME_CANCELLED
                        result.message = 'task cancellation requested'
                        if goal_handle.is_cancel_requested:
                            goal_handle.canceled()
                        else:
                            goal_handle.abort()
                    else:
                        result.outcome = ExecuteTask.Result.OUTCOME_FAILED
                        result.message = message
                        step_results.append(self._step_result(
                            step, TaskStepResult.OUTCOME_FAILED,
                            ERROR_CAPABILITY_UNAVAILABLE, message))
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
            result.step_results = step_results
            return result
        except Exception as error:
            return self._unexpected_execution_failure(
                goal_handle, plan, current_step, step_results, error)
        finally:
            if owns_active_task:
                with self._lock:
                    self._active_goal = None
                    self._active_lower_goal = None
                    self._active_lower_result = None
                    self._pending_lower_submission = None
                    self._active_cancel_event = None
                    self._lower_cancellation_in_progress = False
                    self._lower_cancellation_complete.clear()
                    self._lower_cancellation_result = None
                    self._execution_idle.set()

    def _unexpected_execution_failure(
            self, goal_handle, plan, current_step, step_results, error):
        """Convert any unexpected execute-path exception into a failed task."""
        error_text = str(error) or type(error).__name__
        message = 'task execution failed: ' + error_text
        with self._lock:
            lower_action_pending = (
                self._active_lower_goal is not None
                or self._pending_lower_submission is not None)
        if lower_action_pending:
            stopped, cancellation_message = self._cancel_lower_and_wait()
            if not stopped:
                message += '; ' + cancellation_message

        failed_step = current_step
        if failed_step is None and plan is not None and plan.steps:
            failed_step = plan.steps[0]
        if failed_step is not None:
            failed_id = list(failed_step.step_id.uuid)
            already_recorded = False
            for item in step_results:
                if list(item.step_id.uuid) == failed_id:
                    item.outcome = TaskStepResult.OUTCOME_FAILED
                    item.error_code = ERROR_CAPABILITY_UNAVAILABLE
                    item.message = message
                    already_recorded = True
                    break
            if not already_recorded:
                step_results.append(self._step_result(
                    failed_step, TaskStepResult.OUTCOME_FAILED,
                    ERROR_CAPABILITY_UNAVAILABLE, message))

        result = ExecuteTask.Result()
        result.outcome = ExecuteTask.Result.OUTCOME_FAILED
        result.message = message
        result.step_results = step_results
        try:
            goal_handle.abort()
        except Exception as abort_error:
            self.get_logger().error(
                'failed to mark task goal aborted after execution failure: '
                + str(abort_error))
        try:
            self._publish_execution_failure(message)
        except Exception as diagnostic_error:
            self.get_logger().error(
                'failed to publish task execution diagnostic: '
                + str(diagnostic_error))
        return result

    def _run_step(self, goal_handle, step, index, total, deadline):
        schema = schema_for(step.capability)
        arguments = validate_arguments(schema, step.arguments)
        if schema.name == 'stop':
            stopped, message = self._request_soft_stop()
            return self._step_result(
                step,
                TaskStepResult.OUTCOME_SUCCEEDED if stopped else TaskStepResult.OUTCOME_FAILED,
                0 if stopped else ERROR_TIMEOUT, message)
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
        submission = self._speak_client.send_goal_async(request)
        self._set_pending_submission(submission)
        goal = self._wait(submission, deadline, goal_handle)
        self._clear_pending_submission(submission)
        if goal is None:
            cancellation_failure = self._get_cancellation_failure()
            if cancellation_failure:
                return self._step_result(
                    step, TaskStepResult.OUTCOME_FAILED, ERROR_TIMEOUT, cancellation_failure)
            if self._should_cancel(goal_handle):
                return self._step_result(step, TaskStepResult.OUTCOME_CANCELLED, 0,
                                         'speech cancelled')
            return self._step_result(step, TaskStepResult.OUTCOME_TIMED_OUT, ERROR_TIMEOUT,
                                     'speech action timed out')
        if not goal.accepted:
            return self._step_result(step, TaskStepResult.OUTCOME_REJECTED,
                                     ERROR_CAPABILITY_UNAVAILABLE, 'speech goal rejected')
        result_future = goal.get_result_async()
        self._set_active_lower_goal(goal, result_future)
        action_result = self._wait(result_future, deadline, goal_handle, goal)
        with self._lock:
            self._active_lower_goal = None
            self._active_lower_result = None
        if action_result is None:
            cancellation_failure = self._get_cancellation_failure()
            if cancellation_failure:
                return self._step_result(
                    step, TaskStepResult.OUTCOME_FAILED, ERROR_TIMEOUT, cancellation_failure)
            if self._should_cancel(goal_handle):
                return self._step_result(step, TaskStepResult.OUTCOME_CANCELLED, 0,
                                         'speech cancelled')
            return self._step_result(step, TaskStepResult.OUTCOME_TIMED_OUT, ERROR_TIMEOUT,
                                     'speech action timed out')
        speak_result = action_result.result
        if (action_result.status == GoalStatus.STATUS_SUCCEEDED
                and speak_result.outcome == Speak.Result.OUTCOME_SUCCEEDED):
            return self._step_result(
                step, TaskStepResult.OUTCOME_SUCCEEDED, 0, speak_result.message)
        if (action_result.status == GoalStatus.STATUS_CANCELED
                and speak_result.outcome == Speak.Result.OUTCOME_CANCELLED
                and self._should_cancel(goal_handle)):
            return self._step_result(
                step, TaskStepResult.OUTCOME_CANCELLED, 0,
                speak_result.message or 'speech cancelled')
        message = speak_result.message or (
            'speech action ended with ROS status '
            + _goal_status_name(action_result.status))
        return self._step_result(
            step, TaskStepResult.OUTCOME_FAILED,
            ERROR_CAPABILITY_UNAVAILABLE, message)

    def _run_navigation(self, goal_handle, step, arguments, index, total, deadline):
        attempts = 1 + self.get_parameter('navigation_recovery_attempts').value
        last = None
        for attempt in range(attempts):
            if attempt:
                self._feedback(goal_handle, ExecuteTask.Feedback.STATE_RECOVERING, index, total,
                               step.capability, 'bounded navigation recovery')
            request = NavigateToNamedLocation.Goal()
            request.location_name = arguments['location']
            submission = self._navigate_client.send_goal_async(request)
            self._set_pending_submission(submission)
            goal = self._wait(submission, deadline, goal_handle)
            self._clear_pending_submission(submission)
            if goal is None:
                cancellation_failure = self._get_cancellation_failure()
                if cancellation_failure:
                    return self._step_result(
                        step, TaskStepResult.OUTCOME_FAILED, ERROR_TIMEOUT, cancellation_failure)
                if self._should_cancel(goal_handle):
                    return self._step_result(step, TaskStepResult.OUTCOME_CANCELLED, 0,
                                             'navigation cancelled')
                return self._step_result(step, TaskStepResult.OUTCOME_TIMED_OUT, ERROR_TIMEOUT,
                                         'navigation action timed out')
            if not goal.accepted:
                return self._step_result(step, TaskStepResult.OUTCOME_REJECTED,
                                         ERROR_CAPABILITY_UNAVAILABLE, 'navigation goal rejected')
            result_future = goal.get_result_async()
            self._set_active_lower_goal(goal, result_future)
            action_result = self._wait(result_future, deadline, goal_handle, goal)
            with self._lock:
                self._active_lower_goal = None
                self._active_lower_result = None
            if action_result is None:
                cancellation_failure = self._get_cancellation_failure()
                if cancellation_failure:
                    return self._step_result(
                        step, TaskStepResult.OUTCOME_FAILED, ERROR_TIMEOUT, cancellation_failure)
                if self._should_cancel(goal_handle):
                    return self._step_result(step, TaskStepResult.OUTCOME_CANCELLED, 0,
                                             'navigation cancelled')
                return self._step_result(step, TaskStepResult.OUTCOME_TIMED_OUT, ERROR_TIMEOUT,
                                         'navigation action timed out')
            nav_result = action_result.result
            if (action_result.status == GoalStatus.STATUS_SUCCEEDED
                    and nav_result.outcome
                    == NavigateToNamedLocation.Result.OUTCOME_SUCCEEDED):
                return self._step_result(
                    step, TaskStepResult.OUTCOME_SUCCEEDED, 0, nav_result.message)
            if (action_result.status == GoalStatus.STATUS_CANCELED
                    and nav_result.outcome
                    == NavigateToNamedLocation.Result.OUTCOME_CANCELLED
                    and self._should_cancel(goal_handle)):
                return self._step_result(
                    step, TaskStepResult.OUTCOME_CANCELLED, 0,
                    nav_result.message or 'navigation cancelled')
            last = nav_result.message or (
                'navigation action ended with ROS status '
                + _goal_status_name(action_result.status))
            if nav_result.outcome in (
                    NavigateToNamedLocation.Result.OUTCOME_CANCELLED,
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
                stopped, message = self._cancel_lower_and_wait()
                if not stopped:
                    self._remember_cancellation_failure(message)
                return None
            time.sleep(0.01)
        if not future.done():
            stopped, message = self._cancel_lower_and_wait()
            if not stopped:
                self._remember_cancellation_failure(message)
            return None
        return future.result()

    def _request_soft_stop(self) -> tuple[bool, str]:
        with self._lock:
            event = self._active_cancel_event
        if event is not None:
            event.set()
        stopped, message = self._cancel_lower_and_wait()
        if not stopped:
            self._remember_cancellation_failure(message)
        return stopped, message

    def _cancel_lower_and_wait(self) -> tuple[bool, str]:
        with self._lock:
            if self._lower_cancellation_in_progress:
                wait_for_existing = True
            else:
                wait_for_existing = False
                self._lower_cancellation_in_progress = True
                self._lower_cancellation_complete.clear()
        if wait_for_existing:
            timeout = self._bounded_cancellation_wait_seconds()
            if not self._lower_cancellation_complete.wait(timeout):
                result = (False, 'lower action cancellation did not complete before bound')
                self._quarantine_unresolved_lower_action(result[1])
                return result
            with self._lock:
                return self._lower_cancellation_result
        result = (False, 'lower action cancellation raised an internal exception')
        try:
            result = self._cancel_lower_and_wait_once()
        except Exception as error:  # Lower action transport failures are structured task failures.
            result = (False, 'lower action cancellation failed: ' + str(error))
        finally:
            if not result[0]:
                self._quarantine_unresolved_lower_action(result[1])
            with self._lock:
                self._lower_cancellation_result = result
                self._lower_cancellation_in_progress = False
                self._lower_cancellation_complete.set()
        return result

    def _cancel_lower_and_wait_once(self) -> tuple[bool, str]:
        if self._release_quarantined_lower_if_terminal():
            return True, 'quarantined lower action reached a terminal result'
        with self._lock:
            goal = (
                self._quarantined_lower_goal
                if self._quarantined_lower_goal is not None else self._active_lower_goal)
            result_future = (
                self._quarantined_lower_result
                if self._quarantined_lower_goal is not None else self._active_lower_result)
            submission = (
                self._quarantined_lower_submission
                if self._quarantined_lower_submission is not None
                else self._pending_lower_submission)
        if submission is not None:
            deadline = self._cancellation_deadline()
            while not submission.done() and time.monotonic() < deadline:
                time.sleep(0.01)
            if not submission.done():
                return False, (
                    'lower action goal submission did not resolve before cancellation bound')
            try:
                goal = submission.result()
            except Exception:
                # A failed request can never become an accepted lower action.
                self._clear_quarantined_submission(submission)
                return True, 'lower action goal submission failed before execution'
            if not goal.accepted:
                self._clear_quarantined_submission(submission)
                return True, 'lower action goal was rejected before execution'
            result_future = goal.get_result_async()
            quarantined_goal = False
            with self._lock:
                if self._quarantined_lower_submission is submission:
                    self._quarantined_lower_submission = None
                    self._quarantined_lower_goal = goal
                    self._quarantined_lower_result = result_future
                    quarantined_goal = True
                else:
                    self._active_lower_goal = goal
                    self._active_lower_result = result_future
                    if self._pending_lower_submission is submission:
                        self._pending_lower_submission = None
            if quarantined_goal:
                result_future.add_done_callback(
                    lambda done, owned_goal=goal:
                    self._on_quarantined_lower_terminal(owned_goal, done))
        if goal is not None:
            if result_future is None:
                result_future = goal.get_result_async()
            result = self._cancel_lower_action(goal, result_future)
            if result[0]:
                self._clear_quarantined_goal(goal)
            return result
        return True, 'no lower action was active'

    def _cancel_lower_action(self, goal, result_future) -> tuple[bool, str]:
        deadline = self._cancellation_deadline()
        cancellation = goal.cancel_goal_async()
        while not cancellation.done() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not cancellation.done():
            return False, 'lower action cancellation acknowledgement timed out'
        try:
            cancellation_result = cancellation.result()
        except Exception as error:
            return False, (
                'lower action cancellation acknowledgement failed: ' + str(error))
        if not cancellation_result.goals_canceling:
            return False, 'lower action did not acknowledge cancellation'
        while not result_future.done() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not result_future.done():
            return False, 'lower action did not reach a terminal result after cancellation'
        try:
            terminal = result_future.result()
        except Exception as error:
            return False, 'lower action result failed after cancellation: ' + str(error)
        if terminal.status != GoalStatus.STATUS_CANCELED:
            return False, (
                'lower action cancellation could not be confirmed: terminal ROS status '
                + _goal_status_name(terminal.status))
        terminal_result = terminal.result
        if isinstance(terminal_result, Speak.Result):
            custom_cancelled = (
                terminal_result.outcome == Speak.Result.OUTCOME_CANCELLED)
        elif isinstance(terminal_result, NavigateToNamedLocation.Result):
            custom_cancelled = (
                terminal_result.outcome
                == NavigateToNamedLocation.Result.OUTCOME_CANCELLED)
        else:
            custom_cancelled = False
        if not custom_cancelled:
            return False, (
                'lower action cancellation could not be confirmed: '
                'terminal payload was not cancelled')
        return True, 'lower action cancellation completed'

    def _set_pending_submission(self, submission) -> None:
        with self._lock:
            self._pending_lower_submission = submission

    def _clear_pending_submission(self, submission) -> None:
        with self._lock:
            if self._pending_lower_submission is submission:
                self._pending_lower_submission = None

    def _set_active_lower_goal(self, goal, result_future) -> None:
        with self._lock:
            self._active_lower_goal = goal
            self._active_lower_result = result_future

    def _has_quarantined_lower_action_locked(self) -> bool:
        return (
            self._quarantined_lower_goal is not None
            or self._quarantined_lower_submission is not None)

    def _quarantine_unresolved_lower_action(self, reason: str) -> None:
        """
        Retain ownership until a terminal lower-action result is observed.

        A bounded outer task result is important for callers, but it is not
        evidence that a lower action stopped.  This separate ownership record
        prevents a subsequent side-effecting task from being admitted into an
        ambiguous lower-action state.
        """
        terminal_to_watch = None
        submission_to_watch = None
        with self._lock:
            if self._has_quarantined_lower_action_locked():
                if not self._quarantine_reason:
                    self._quarantine_reason = reason
                return
            goal = self._active_lower_goal
            result_future = self._active_lower_result
            submission = self._pending_lower_submission
            if result_future is not None and result_future.done():
                # The cancellation protocol failed, but the lower action has
                # already reached a terminal state.  Retrieve that outcome and
                # do not quarantine a non-running action.
                try:
                    result_future.result()
                except Exception:
                    pass
                return
            self._quarantine_reason = reason
            if goal is not None:
                if result_future is None:
                    result_future = goal.get_result_async()
                self._quarantined_lower_goal = goal
                self._quarantined_lower_result = result_future
                terminal_to_watch = (goal, result_future)
            elif submission is not None:
                self._quarantined_lower_submission = submission
                submission_to_watch = submission
        if terminal_to_watch is not None:
            goal, result_future = terminal_to_watch
            result_future.add_done_callback(
                lambda done, owned_goal=goal:
                self._on_quarantined_lower_terminal(owned_goal, done))
        if submission_to_watch is not None:
            submission_to_watch.add_done_callback(self._on_quarantined_submission)

    def _release_quarantined_lower_if_terminal(self) -> bool:
        with self._lock:
            result_future = self._quarantined_lower_result
        if result_future is None or not result_future.done():
            return False
        # Retrieve the terminal outcome even when it is an exception.  Either
        # form proves that the lower action can no longer execute.
        try:
            result_future.result()
        except Exception:
            pass
        with self._lock:
            if self._quarantined_lower_result is result_future:
                self._quarantined_lower_goal = None
                self._quarantined_lower_result = None
                self._quarantine_reason = ''
                return True
        return False

    def _clear_quarantined_goal(self, goal) -> None:
        with self._lock:
            if self._quarantined_lower_goal is goal:
                self._quarantined_lower_goal = None
                self._quarantined_lower_result = None
                self._quarantine_reason = ''

    def _clear_quarantined_submission(self, submission) -> None:
        with self._lock:
            if self._quarantined_lower_submission is submission:
                self._quarantined_lower_submission = None
                self._quarantine_reason = ''

    def _on_quarantined_lower_terminal(self, goal, result_future) -> None:
        """Release a quarantined goal only after its terminal future resolves."""
        # rclpy invokes this from an executor callback.  Do not block here:
        # obtaining the result is enough to observe terminal ownership.
        try:
            result_future.result()
        except Exception:
            pass
        self._clear_quarantined_goal(goal)

    def _on_quarantined_submission(self, submission) -> None:
        """Cancel a late accepted submission without leaving an ownership gap."""
        try:
            goal = submission.result()
        except Exception:
            self._clear_quarantined_submission(submission)
            return
        if not goal.accepted:
            self._clear_quarantined_submission(submission)
            return
        result_future = goal.get_result_async()
        terminal_to_watch = False
        with self._lock:
            if self._quarantined_lower_submission is not submission:
                return
            self._quarantined_lower_submission = None
            self._quarantined_lower_goal = goal
            self._quarantined_lower_result = result_future
            terminal_to_watch = True
        if terminal_to_watch:
            result_future.add_done_callback(
                lambda done, owned_goal=goal:
                self._on_quarantined_lower_terminal(owned_goal, done))
        try:
            goal.cancel_goal_async()
        except Exception:
            # Retain quarantine; only a terminal lower result may release it.
            pass

    def _remember_cancellation_failure(self, message: str) -> None:
        with self._lock:
            if not self._cancellation_failure:
                self._cancellation_failure = message

    def _get_cancellation_failure(self) -> str:
        with self._lock:
            return self._cancellation_failure

    def _cancellation_deadline(self) -> float:
        """Return the normal cancellation bound clipped by shutdown grace."""
        deadline = time.monotonic() + self.get_parameter(
            'cancellation_wait_seconds').value
        with self._lock:
            shutdown_deadline = self._shutdown_deadline
        if shutdown_deadline is not None:
            deadline = min(deadline, shutdown_deadline)
        return deadline

    def _bounded_cancellation_wait_seconds(self) -> float:
        return max(0.0, self._cancellation_deadline() - time.monotonic())

    def _should_cancel(self, goal_handle) -> bool:
        with self._lock:
            event = self._active_cancel_event
        return goal_handle.is_cancel_requested or (event is not None and event.is_set())

    def request_shutdown(self) -> None:
        """Request normal task cancellation before ROS entities are destroyed."""
        deadline = time.monotonic() + self.shutdown_timeout_seconds()
        with self._lock:
            event = self._active_cancel_event
            active = self._active_goal is not None
            if active and self._shutdown_deadline is None:
                self._shutdown_deadline = deadline
        if event is not None:
            event.set()
        if not active:
            self._execution_idle.set()

    def shutdown_complete(self) -> bool:
        """Report whether the active ExecuteTask callback has left its critical path."""
        return self._execution_idle.is_set()

    def shutdown_timeout_seconds(self) -> float:
        """Bound active-task draining while preserving time for executor teardown."""
        cancellation_bound = self.get_parameter('cancellation_wait_seconds').value
        # ros2 launch gives this process a five-second SIGINT grace period.  A
        # running task can use two lower-action waits (submission then terminal
        # cancellation), but its total shutdown work is clipped to 3.5 seconds.
        # The remaining budget is reserved for callback retrieval, thread-pool
        # closure, entity destruction, and rclpy shutdown.
        return min(3.5, max(0.1, (2.0 * cancellation_bound) + 0.25))

    def destroy_node(self) -> None:
        """Destroy action waitables before standard Node-owned entities."""
        with self._lock:
            if self._owned_actions_destroyed:
                return
            self._owned_actions_destroyed = True
        self._server.destroy()
        self._speak_client.destroy()
        self._navigate_client.destroy()
        super().destroy_node()

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
            quarantined = self._has_quarantined_lower_action_locked()
            quarantine_reason = self._quarantine_reason
        status = DiagnosticStatus()
        status.name = 'buddy_task_executive'
        status.hardware_id = 'buddy'
        status.level = DiagnosticStatus.ERROR if quarantined else DiagnosticStatus.OK
        status.message = (
            'lower action cancellation unresolved: ' + quarantine_reason
            if quarantined else 'task executive active')
        status.values = [
            KeyValue(key='active_task', value=str(active).lower()),
            KeyValue(key='lower_action_quarantined', value=str(quarantined).lower()),
        ]
        message = DiagnosticArray()
        message.header.stamp = self.get_clock().now().to_msg()
        message.status = [status]
        self._diagnostics.publish(message)

    def _publish_execution_failure(self, failure_message: str) -> None:
        with self._lock:
            active = self._active_goal is not None
            quarantined = self._has_quarantined_lower_action_locked()
        status = DiagnosticStatus()
        status.name = 'buddy_task_executive'
        status.hardware_id = 'buddy'
        status.level = DiagnosticStatus.ERROR
        status.message = failure_message
        status.values = [
            KeyValue(key='active_task', value=str(active).lower()),
            KeyValue(key='lower_action_quarantined', value=str(quarantined).lower()),
        ]
        message = DiagnosticArray()
        message.header.stamp = self.get_clock().now().to_msg()
        message.status = [status]
        self._diagnostics.publish(message)


def _failure(code, message, step_index):
    from buddy_task_executor.validation import ValidationFailure
    return ValidationFailure(code, message, step_index)


def _goal_status_name(status: int) -> str:
    names = {
        GoalStatus.STATUS_UNKNOWN: 'UNKNOWN',
        GoalStatus.STATUS_ACCEPTED: 'ACCEPTED',
        GoalStatus.STATUS_EXECUTING: 'EXECUTING',
        GoalStatus.STATUS_CANCELING: 'CANCELING',
        GoalStatus.STATUS_SUCCEEDED: 'SUCCEEDED',
        GoalStatus.STATUS_CANCELED: 'CANCELED',
        GoalStatus.STATUS_ABORTED: 'ABORTED',
    }
    return names.get(status, f'INVALID({status})')


def _drain_active_task(node, executor) -> None:
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
    node = TaskExecutive()
    executor = DrainingMultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        _drain_active_task(node, executor)
    finally:
        try:
            cancelled_sources = executor.drain_submitted_callbacks(0.25)
        except (KeyboardInterrupt, ExternalShutdownException):
            cancelled_sources = ()
        except Exception as error:
            # Do not skip the bounded executor/node cleanup if a third-party
            # callback misbehaves.  A completed callback exception has already
            # been retrieved by drain_submitted_callbacks.
            cancelled_sources = ()
            node.get_logger().error('callback drain failed during shutdown: ' + str(error))
        if cancelled_sources:
            node.get_logger().info(
                'cancelled queued callbacks before shutdown: '
                + ', '.join(cancelled_sources)
            )
        try:
            if not executor.shutdown(timeout_sec=0.25):
                node.get_logger().error('executor workers did not stop before shutdown bound')
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
