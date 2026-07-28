"""Component tests keep task execution isolated from neighbor implementations."""

import os
from test.mock_action_servers import MockCapabilityActionServers
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from action_msgs.msg import GoalStatus
from buddy_capabilities.catalog import TYPE_STRING
from buddy_interfaces.action import ExecuteTask, NavigateToNamedLocation
from buddy_interfaces.msg import (
    NamedLocation, RobotStatus, SafetyState, TaskArgument, TaskPlan, TaskStep, TaskStepResult,
    WorldSummary)
from buddy_task_executor.executive import TaskExecutive
from diagnostic_msgs.msg import DiagnosticStatus
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.task import Future


def wait(future, timeout=3.0):
    deadline = time.monotonic() + timeout
    while not future.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    if not future.done():
        raise TimeoutError('ROS future did not complete')
    return future.result()


def identifier(value):
    from unique_identifier_msgs.msg import UUID
    result = UUID()
    result.uuid = [value] * 16
    return result


class FakeLowerGoal:
    """Accepted lower goal with deterministic transport-future failures."""

    accepted = True

    def __init__(self, *, result_error=None, cancel_error=None):
        self._result = Future()
        if result_error is not None:
            self._result.set_exception(result_error)
        self._cancel_error = cancel_error

    def get_result_async(self):
        return self._result

    def cancel_goal_async(self):
        cancellation = Future()
        if self._cancel_error is not None:
            cancellation.set_exception(self._cancel_error)
        else:
            cancellation.set_result(SimpleNamespace(goals_canceling=[object()]))
        return cancellation


class TaskExecutiveComponentTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('ROS_LOG_DIR', '/tmp')
        os.environ.setdefault('FASTDDS_BUILTIN_TRANSPORTS', 'SHM')
        rclpy.init()
        cls.executive = TaskExecutive()
        cls.executive.set_parameters([
            Parameter('cancellation_wait_seconds', Parameter.Type.DOUBLE, 0.3)])
        cls.mocks = MockCapabilityActionServers()
        cls.probe = Node('task_executive_component_probe')
        cls.executor = MultiThreadedExecutor(num_threads=4)
        for node in (cls.executive, cls.mocks, cls.probe):
            cls.executor.add_node(node)
        cls.spin_thread = threading.Thread(target=cls.executor.spin, daemon=True)
        cls.spin_thread.start()
        cls.client = ActionClient(cls.probe, ExecuteTask, '/buddy/tasks/execute')
        assert cls.client.wait_for_server(timeout_sec=2.0)
        status_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                                durability=DurabilityPolicy.TRANSIENT_LOCAL)
        cls.status_publisher = cls.probe.create_publisher(RobotStatus, '/buddy/status', status_qos)
        cls.world_publisher = cls.probe.create_publisher(
            WorldSummary, '/buddy/world/summary', status_qos)
        status = RobotStatus()
        status.localization_state = RobotStatus.LOCALIZATION_GOOD
        status.motion_ready = True
        status.safety.state = SafetyState.STATE_NORMAL
        status.safety.motion_permitted = True
        cls.status_publisher.publish(status)
        world = WorldSummary()
        location = NamedLocation()
        location.name = 'kitchen'
        location.enabled = True
        world.named_locations = [location]
        cls.world_publisher.publish(world)
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.executor.shutdown()
        cls.spin_thread.join(timeout=2.0)
        for node in (cls.probe, cls.mocks, cls.executive):
            node.destroy_node()
        rclpy.shutdown()

    @staticmethod
    def _plan(capability, argument_name='text', argument_value='hello', timeout=5):
        plan = TaskPlan()
        plan.plan_id = identifier(1)
        plan.session_id = identifier(9)
        plan.user_confirmed = True
        step = TaskStep()
        step.step_id = identifier(2)
        step.capability = capability
        step.timeout.sec = timeout
        if argument_name:
            argument = TaskArgument()
            argument.name = argument_name
            argument.value_type = TYPE_STRING
            argument.value = argument_value
            step.arguments = [argument]
        plan.steps = [step]
        return plan

    def _result(self, plan):
        return self._wrapped_result(plan).result

    def _wrapped_result(self, plan):
        goal = ExecuteTask.Goal()
        goal.plan = plan
        goal_handle = wait(self.client.send_goal_async(goal))
        self.assertTrue(goal_handle.accepted)
        return wait(goal_handle.get_result_async())

    def _send(self, plan, feedback_callback=None):
        goal = ExecuteTask.Goal()
        goal.plan = plan
        return wait(self.client.send_goal_async(goal, feedback_callback=feedback_callback))

    def test_executes_speak_through_deterministic_mock_action(self):
        wrapped = self._wrapped_result(self._plan('speak'))
        result = wrapped.result
        self.assertEqual(wrapped.status, GoalStatus.STATUS_SUCCEEDED)
        self.assertEqual(result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)
        self.assertEqual(result.step_results[0].outcome, 0)
        self.assertEqual(self.mocks.speak_requests[-1].text, 'hello')

    def test_lower_aborts_with_default_success_payload_are_task_failures(self):
        cases = (
            ('speak', 'text', 'hello', 'speak_terminal_status'),
            ('navigate_to', 'location', 'kitchen', 'navigation_terminal_status'),
        )
        for capability, argument_name, argument_value, mode_attribute in cases:
            setattr(self.mocks, mode_attribute, 'aborted')
            try:
                wrapped = self._wrapped_result(
                    self._plan(capability, argument_name, argument_value))
            finally:
                setattr(self.mocks, mode_attribute, 'succeeded')
            self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
            self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
            self.assertEqual(
                wrapped.result.step_results[0].outcome,
                TaskStepResult.OUTCOME_FAILED)
            self.assertTrue(wrapped.result.message)

    def test_submission_future_exception_is_structured_and_releases_reservation(self):
        failed_submission = Future()
        failed_submission.set_exception(RuntimeError('submission transport failed'))
        with (
                patch.object(self.executive._diagnostics, 'publish') as publish,
                patch.object(
                    self.executive._speak_client, 'send_goal_async',
                    return_value=failed_submission)):
            wrapped = self._wrapped_result(self._plan('speak'))

        self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
        self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
        self.assertTrue(wrapped.result.step_results)
        self.assertIn('submission transport failed', wrapped.result.message)
        self.assertTrue(any(
            call.args[0].status[0].level == DiagnosticStatus.ERROR
            and 'submission transport failed' in call.args[0].status[0].message
            for call in publish.call_args_list))

        recovery = self._wrapped_result(self._plan('speak'))
        self.assertEqual(recovery.status, GoalStatus.STATUS_SUCCEEDED)
        self.assertEqual(recovery.result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)

    def test_result_future_exception_is_structured_and_releases_reservation(self):
        lower_goal = FakeLowerGoal(
            result_error=RuntimeError('result transport failed'))
        submission = Future()
        submission.set_result(lower_goal)
        with patch.object(
                self.executive._speak_client, 'send_goal_async',
                return_value=submission):
            wrapped = self._wrapped_result(self._plan('speak'))

        self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
        self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
        self.assertTrue(wrapped.result.step_results)
        self.assertIn('result transport failed', wrapped.result.message)

        recovery = self._wrapped_result(self._plan('speak'))
        self.assertEqual(recovery.status, GoalStatus.STATUS_SUCCEEDED)
        self.assertEqual(recovery.result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)

    def test_cancel_future_exception_is_structured_and_releases_reservation(self):
        lower_goal = FakeLowerGoal(
            cancel_error=RuntimeError('cancel transport failed'))
        submission = Future()
        submission.set_result(lower_goal)
        with patch.object(
                self.executive._speak_client, 'send_goal_async',
                return_value=submission):
            goal_handle = self._send(self._plan('speak'))
            time.sleep(0.05)
            wait(goal_handle.cancel_goal_async())
            wrapped = wait(goal_handle.get_result_async())

        self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
        self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
        self.assertIn('cancel transport failed', wrapped.result.message)

        recovery = self._wrapped_result(self._plan('speak'))
        self.assertEqual(recovery.status, GoalStatus.STATUS_SUCCEEDED)
        self.assertEqual(recovery.result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)

    def test_unknown_capability_returns_structured_rejection_without_side_effect(self):
        before = len(self.mocks.speak_requests)
        result = self._result(self._plan('not_registered', argument_name=''))
        self.assertEqual(result.outcome, ExecuteTask.Result.OUTCOME_REJECTED)
        self.assertEqual(result.step_results[0].outcome, 2)
        self.assertEqual(len(self.mocks.speak_requests), before)

    def test_speak_timeout_cancels_mock_action_and_returns_timed_out_step(self):
        self.mocks.hold_speak = True
        try:
            wrapped = self._wrapped_result(self._plan('speak', timeout=1))
        finally:
            self.mocks.hold_speak = False
        result = wrapped.result
        self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
        self.assertEqual(result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
        self.assertEqual(result.step_results[0].outcome, 3)

    def test_task_cancellation_cancels_active_action_and_emits_feedback(self):
        feedback = []
        self.mocks.hold_speak = True
        try:
            goal_handle = self._send(
                self._plan('speak'), lambda message: feedback.append(message.feedback.state))
            time.sleep(0.1)
            wait(goal_handle.cancel_goal_async())
            wrapped = wait(goal_handle.get_result_async())
        finally:
            self.mocks.hold_speak = False
        result = wrapped.result
        self.assertEqual(wrapped.status, GoalStatus.STATUS_CANCELED)
        self.assertEqual(result.outcome, ExecuteTask.Result.OUTCOME_CANCELLED)
        self.assertIn(ExecuteTask.Feedback.STATE_EXECUTING, feedback)

    def test_cancel_acknowledged_but_wrong_terminal_status_fails_safe(self):
        for terminal_status in ('aborted', 'succeeded'):
            self.mocks.hold_speak = True
            self.mocks.cancel_terminal_status = terminal_status
            try:
                goal_handle = self._send(self._plan('speak'))
                time.sleep(0.1)
                wait(goal_handle.cancel_goal_async())
                wrapped = wait(goal_handle.get_result_async())
            finally:
                self.mocks.hold_speak = False
                self.mocks.cancel_terminal_status = 'canceled'
            self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
            self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
            self.assertIn('cancellation', wrapped.result.message)

    def test_registered_stop_cancels_an_active_task(self):
        self.mocks.hold_speak = True
        try:
            active = self._send(self._plan('speak'))
            time.sleep(0.1)
            stop_result = self._result(self._plan('stop', argument_name=''))
            active_result = wait(active.get_result_async()).result
        finally:
            self.mocks.hold_speak = False
        self.assertEqual(
            stop_result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED, stop_result.message)
        self.assertEqual(active_result.outcome, ExecuteTask.Result.OUTCOME_CANCELLED)

    def test_stop_cancels_a_goal_that_was_pending_acceptance(self):
        self.mocks.hold_speak = True
        self.mocks.goal_accept_delay_seconds = 0.2
        try:
            active = self._send(self._plan('speak'))
            time.sleep(0.05)
            stop_result = self._result(self._plan('stop', argument_name=''))
            active_result = wait(active.get_result_async()).result
        finally:
            self.mocks.hold_speak = False
            self.mocks.goal_accept_delay_seconds = 0.0
        self.assertEqual(stop_result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)
        self.assertEqual(active_result.outcome, ExecuteTask.Result.OUTCOME_CANCELLED)

    def test_stop_fails_when_lower_action_rejects_cancellation(self):
        self.mocks.hold_speak = True
        self.mocks.accept_cancellation = False
        try:
            active = self._send(self._plan('speak'))
            time.sleep(0.1)
            stop_result = self._result(self._plan('stop', argument_name=''))
            active_result = wait(active.get_result_async()).result
        finally:
            self.mocks.hold_speak = False
            self.mocks.accept_cancellation = True
        self.assertEqual(stop_result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
        self.assertEqual(stop_result.step_results[0].outcome, 4)
        self.assertEqual(active_result.outcome, ExecuteTask.Result.OUTCOME_FAILED)

    def test_registered_stop_awaits_navigation_cancellation(self):
        self.mocks.hold_navigation = True
        try:
            active = self._send(
                self._plan('navigate_to', 'location', 'kitchen'))
            time.sleep(0.1)
            stop_result = self._result(self._plan('stop', argument_name=''))
            active_result = wait(active.get_result_async()).result
        finally:
            self.mocks.hold_navigation = False
        self.assertEqual(stop_result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)
        self.assertEqual(active_result.outcome, ExecuteTask.Result.OUTCOME_CANCELLED)
        self.assertEqual(self.mocks.navigation_requests[-1].location_name, 'kitchen')

    def test_shutdown_request_cancels_and_drains_active_action_before_bound(self):
        self.mocks.hold_speak = True
        try:
            active = self._send(self._plan('speak'))
            time.sleep(0.1)
            self.executive.request_shutdown()
            deadline = time.monotonic() + self.executive.shutdown_timeout_seconds()
            while not self.executive.shutdown_complete() and time.monotonic() < deadline:
                time.sleep(0.01)
            active_result = wait(active.get_result_async()).result
        finally:
            self.mocks.hold_speak = False
        self.assertTrue(self.executive.shutdown_complete())
        self.assertEqual(active_result.outcome, ExecuteTask.Result.OUTCOME_CANCELLED)

    def test_terminal_navigation_failures_are_structured_without_retry(self):
        terminal_outcomes = (
            NavigateToNamedLocation.Result.OUTCOME_SAFETY_STOP,
            NavigateToNamedLocation.Result.OUTCOME_UNKNOWN_LOCATION,
            NavigateToNamedLocation.Result.OUTCOME_LOCALIZATION_UNAVAILABLE)
        for outcome in terminal_outcomes:
            self.mocks.navigation_outcome = outcome
            before = len(self.mocks.navigation_requests)
            result = self._result(self._plan('navigate_to', 'location', 'kitchen'))
            self.assertEqual(result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
            self.assertTrue(result.step_results[0].message)
            self.assertEqual(len(self.mocks.navigation_requests), before + 1)
        self.mocks.navigation_outcome = NavigateToNamedLocation.Result.OUTCOME_SUCCEEDED
