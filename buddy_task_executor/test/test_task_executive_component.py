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
from buddy_interfaces.action import ExecuteTask, NavigateToNamedLocation, Speak
from buddy_interfaces.msg import (
    EmergencyStopRequest, NamedLocation, RobotStatus, SafetyState, TaskArgument, TaskPlan,
    TaskStep, TaskStepResult, WorldSummary)
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

    def __init__(
            self, *, result_error=None, cancel_error=None,
            cancel_timeout_attempts=0):
        self._result = Future()
        if result_error is not None:
            self._result.set_exception(result_error)
        self._cancel_error = cancel_error
        self._cancel_timeout_attempts = cancel_timeout_attempts
        self.cancel_attempts = 0

    def get_result_async(self):
        return self._result

    def cancel_goal_async(self):
        self.cancel_attempts += 1
        cancellation = Future()
        if self.cancel_attempts <= self._cancel_timeout_attempts:
            return cancellation
        if self._cancel_error is not None:
            cancellation.set_exception(self._cancel_error)
        else:
            cancellation.set_result(SimpleNamespace(goals_canceling=[object()]))
        return cancellation


class MockSafetyEmergencyStopConsumer(Node):
    """Minimal frozen-contract consumer that models latched zero-motion safety."""

    def __init__(self):
        super().__init__('task_executive_safety_probe')
        emergency_qos = QoSProfile(
            depth=10, reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE)
        self.event = threading.Event()
        self.request = None
        self.motion_permitted = True
        self.safe_linear_velocity = 1.0
        self._subscription = self.create_subscription(
            EmergencyStopRequest, '/buddy/safety/emergency_stop/request',
            self._receive, emergency_qos)

    def reset_observation(self):
        self.event.clear()
        self.request = None
        self.motion_permitted = True
        self.safe_linear_velocity = 1.0

    def _receive(self, request):
        self.request = request
        # Mirrors the frozen safety contract: every emergency-stop request
        # latches motion inhibition and commands zero until explicit reset.
        self.motion_permitted = False
        self.safe_linear_velocity = 0.0
        self.event.set()


class TaskExecutiveComponentTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('ROS_LOG_DIR', '/tmp')
        os.environ.setdefault('FASTDDS_BUILTIN_TRANSPORTS', 'SHM')
        rclpy.init()
        cls.executive = TaskExecutive()
        cls.executive.set_parameters([
            Parameter('cancellation_wait_seconds', Parameter.Type.DOUBLE, 0.3),
            Parameter('summary_freshness_seconds', Parameter.Type.DOUBLE, 30.0)])
        cls.mocks = MockCapabilityActionServers()
        cls.probe = Node('task_executive_component_probe')
        cls.safety_probe = MockSafetyEmergencyStopConsumer()
        cls.executor = MultiThreadedExecutor(num_threads=4)
        for node in (cls.executive, cls.mocks, cls.probe, cls.safety_probe):
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
        for node in (cls.safety_probe, cls.probe, cls.mocks, cls.executive):
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

    def _wait_for_quarantine_release(self, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.executive._lock:
                if not self.executive._has_quarantined_lower_action_locked():
                    return
            time.sleep(0.01)
        self.fail('lower action quarantine did not release after terminal completion')

    def _wait_until(self, predicate, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        self.fail('timed out waiting for expected condition')

    def _readiness_diagnostic(self):
        with patch.object(self.executive._diagnostics, 'publish') as publish:
            self.executive._publish_diagnostics()
        return publish.call_args.args[0].status[0]

    @staticmethod
    def _diagnostic_values(diagnostic):
        return {item.key: item.value for item in diagnostic.values}

    def test_readiness_is_false_at_startup_then_expires_by_steady_time(self):
        """No simulated clock progress can keep stale authorization alive."""
        status = RobotStatus()
        status.localization_state = RobotStatus.LOCALIZATION_GOOD
        status.motion_ready = True
        status.safety.state = SafetyState.STATE_NORMAL
        status.safety.motion_permitted = True
        world = WorldSummary()
        location = NamedLocation()
        location.name = 'kitchen'
        location.enabled = True
        world.named_locations = [location]

        with self.executive._lock:
            original = (
                self.executive._status,
                self.executive._world,
                self.executive._status_received_monotonic,
                self.executive._world_received_monotonic,
            )
            self.executive._status = None
            self.executive._world = None
            self.executive._status_received_monotonic = None
            self.executive._world_received_monotonic = None
        self.executive.set_parameters([
            Parameter('summary_freshness_seconds', Parameter.Type.DOUBLE, 0.5)])
        try:
            with patch('buddy_task_executor.executive.time.monotonic', return_value=100.0):
                startup = self._readiness_diagnostic()
                self.assertEqual(startup.level, DiagnosticStatus.WARN)
                self.assertIn('not ready', startup.message)
                self.assertEqual(self._diagnostic_values(startup), {
                    'active_task': 'false',
                    'lower_action_quarantined': 'false',
                    'status_ready': 'false',
                    'world_ready': 'false',
                    'navigation_ready': 'true',
                    'speech_ready': 'true',
                    'accepting_tasks': 'false',
                })
                self.assertEqual(
                    self.executive._available('report_status'),
                    (False, 'robot status unavailable or stale'))
                self.assertEqual(
                    self.executive._precondition('navigate_to', {'location': 'kitchen'}),
                    'robot status or world summary unavailable or stale')
                self.executive._status_callback(status)
                self.executive._world_callback(world)
                ready = self._readiness_diagnostic()

            self.assertEqual(ready.level, DiagnosticStatus.OK)
            self.assertEqual(ready.message, 'task executive ready')
            self.assertTrue(all(
                value == 'true' for key, value in self._diagnostic_values(ready).items()
                if key in {
                    'status_ready', 'world_ready', 'navigation_ready', 'speech_ready',
                    'accepting_tasks'}))

            with patch('buddy_task_executor.executive.time.monotonic', return_value=100.51):
                expired = self._readiness_diagnostic()
                self.assertEqual(expired.level, DiagnosticStatus.WARN)
                self.assertEqual(
                    self.executive._precondition('navigate_to', {'location': 'kitchen'}),
                    'robot status or world summary unavailable or stale')
                self.assertEqual(
                    self.executive._available('report_status'),
                    (False, 'robot status unavailable or stale'))
            values = self._diagnostic_values(expired)
            self.assertEqual(values['status_ready'], 'false')
            self.assertEqual(values['world_ready'], 'false')
            self.assertEqual(values['accepting_tasks'], 'false')

            with patch.object(
                    self.executive._navigate_client, 'server_is_ready', return_value=False):
                with patch('buddy_task_executor.executive.time.monotonic', return_value=100.0):
                    self.executive._status_callback(status)
                    self.executive._world_callback(world)
                    no_navigation = self._readiness_diagnostic()
            self.assertEqual(no_navigation.level, DiagnosticStatus.WARN)
            self.assertEqual(
                self._diagnostic_values(no_navigation)['navigation_ready'], 'false')
        finally:
            with self.executive._lock:
                (self.executive._status,
                 self.executive._world,
                 self.executive._status_received_monotonic,
                 self.executive._world_received_monotonic) = original
            self.executive.set_parameters([
                Parameter('summary_freshness_seconds', Parameter.Type.DOUBLE, 30.0)])

    def test_summary_freshness_configuration_must_be_finite_and_positive(self):
        for value in (0.0, float('nan'), float('inf')):
            with self.subTest(value=value):
                override = Parameter(
                    'summary_freshness_seconds', Parameter.Type.DOUBLE, value)
                with self.assertRaisesRegex(
                        ValueError,
                        'summary_freshness_seconds must be finite and greater than zero'):
                    TaskExecutive(parameter_overrides=[override])

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
            result_error=RuntimeError('lower action reached terminal transport failure'),
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

    def test_unconfirmed_lower_cancellation_quarantines_side_effects_until_stop_confirms(self):
        """A bounded outer failure must not orphan a possibly live lower action."""
        cases = (
            ('cancellation acknowledgement timed out', 1),
            ('did not reach a terminal result after cancellation', 0),
        )
        for expected_message, cancel_timeout_attempts in cases:
            with self.subTest(expected_message=expected_message):
                lower_goal = FakeLowerGoal(
                    cancel_timeout_attempts=cancel_timeout_attempts)
                submission = Future()
                submission.set_result(lower_goal)
                with patch.object(
                        self.executive._speak_client, 'send_goal_async',
                        return_value=submission):
                    active = self._send(self._plan('speak'))
                    time.sleep(0.05)
                    wait(active.cancel_goal_async())
                    wrapped = wait(active.get_result_async())

                self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
                self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
                self.assertIn(expected_message, wrapped.result.message)
                with self.executive._lock:
                    self.assertIs(self.executive._quarantined_lower_goal, lower_goal)
                    self.assertIsNotNone(self.executive._quarantined_lower_result)

                with patch.object(self.executive._diagnostics, 'publish') as publish:
                    self.executive._publish_diagnostics()
                diagnostic = publish.call_args.args[0].status[0]
                self.assertEqual(diagnostic.level, DiagnosticStatus.ERROR)
                self.assertIn('cancellation unresolved', diagnostic.message)

                blocked = self._wrapped_result(self._plan('speak'))
                self.assertEqual(blocked.status, GoalStatus.STATUS_ABORTED)
                self.assertEqual(blocked.result.outcome, ExecuteTask.Result.OUTCOME_REJECTED)
                self.assertIn('only registered stop is allowed', blocked.result.message)

                def complete_cancelled_result():
                    time.sleep(0.05)
                    terminal = Speak.Result()
                    terminal.outcome = Speak.Result.OUTCOME_CANCELLED
                    terminal.message = 'fake cancellation confirmed'
                    lower_goal._result.set_result(SimpleNamespace(
                        status=GoalStatus.STATUS_CANCELED, result=terminal))

                finisher = threading.Thread(target=complete_cancelled_result)
                finisher.start()
                stop_result = self._result(self._plan('stop', argument_name=''))
                finisher.join(timeout=1.0)
                self.assertFalse(finisher.is_alive())
                self.assertEqual(
                    stop_result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED,
                    stop_result.message)
                self.assertGreaterEqual(lower_goal.cancel_attempts, 2)
                with self.executive._lock:
                    self.assertIsNone(self.executive._quarantined_lower_goal)

                recovery = self._wrapped_result(self._plan('speak'))
                self.assertEqual(recovery.status, GoalStatus.STATUS_SUCCEEDED)
                self.assertEqual(
                    recovery.result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)

    def test_unconfirmed_navigation_cancellation_latches_frozen_emergency_stop(self):
        """A live navigation action that will not cancel escalates to safety."""
        lower_goal = FakeLowerGoal(cancel_timeout_attempts=10)
        submission = Future()
        submission.set_result(lower_goal)
        self.safety_probe.reset_observation()
        with patch.object(
                self.executive._navigate_client, 'send_goal_async',
                return_value=submission):
            active = self._send(self._plan('navigate_to', 'location', 'kitchen'))
            time.sleep(0.05)
            wait(active.cancel_goal_async())
            wrapped = wait(active.get_result_async())

        self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
        self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
        self.assertIn('cancellation acknowledgement timed out', wrapped.result.message)
        with self.executive._lock:
            self.assertIs(self.executive._quarantined_lower_goal, lower_goal)

        self.assertTrue(self.safety_probe.event.wait(1.0))
        request = self.safety_probe.request
        self.assertEqual(request.source, 'buddy_task_executor')
        self.assertEqual(
            request.reason_code, EmergencyStopRequest.REASON_SYSTEM_FAULT)
        self.assertEqual(len(request.request_id.uuid), 16)
        self.assertIn('unresolved lower action cancellation', request.reason)
        self.assertFalse(self.safety_probe.motion_permitted)
        self.assertEqual(self.safety_probe.safe_linear_velocity, 0.0)

        # Discovery represents the KeepLast depth as zero on this Jazzy/Fast
        # DDS combination, so inspect the publisher's configured QoS directly.
        qos = self.executive._emergency_stop.qos_profile
        self.assertEqual(qos.depth, 10)
        self.assertEqual(qos.reliability, ReliabilityPolicy.RELIABLE)
        self.assertEqual(qos.durability, DurabilityPolicy.VOLATILE)

        terminal = NavigateToNamedLocation.Result()
        terminal.outcome = NavigateToNamedLocation.Result.OUTCOME_CANCELLED
        lower_goal._result.set_result(SimpleNamespace(
            status=GoalStatus.STATUS_CANCELED, result=terminal))
        self._wait_for_quarantine_release()

    def test_late_pending_submission_is_canceled_and_quarantined_until_terminal(self):
        """A post-timeout accepted submission cannot create an ownership gap."""
        submission = Future()
        lower_goal = FakeLowerGoal()
        self.safety_probe.reset_observation()
        with patch.object(
                self.executive._speak_client, 'send_goal_async',
                return_value=submission):
            active = self._send(self._plan('speak'))
            time.sleep(0.05)
            wait(active.cancel_goal_async())
            wrapped = wait(active.get_result_async())

        self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
        self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
        self.assertIn('goal submission did not resolve', wrapped.result.message)
        with self.executive._lock:
            self.assertIs(self.executive._quarantined_lower_submission, submission)
        self.assertTrue(self.safety_probe.event.wait(1.0))

        submission.set_result(lower_goal)
        self._wait_until(lambda: lower_goal.cancel_attempts == 1)
        with self.executive._lock:
            self.assertIs(self.executive._quarantined_lower_goal, lower_goal)
            self.assertIsNotNone(self.executive._quarantined_lower_result)

        terminal = Speak.Result()
        terminal.outcome = Speak.Result.OUTCOME_CANCELLED
        lower_goal._result.set_result(SimpleNamespace(
            status=GoalStatus.STATUS_CANCELED, result=terminal))
        self._wait_for_quarantine_release()

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
            with self.executive._lock:
                self.assertIsNone(self.executive._quarantined_lower_goal)

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
        self._wait_for_quarantine_release()
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
            started = time.monotonic()
            self.executive.request_shutdown()
            deadline = time.monotonic() + self.executive.shutdown_timeout_seconds()
            while not self.executive.shutdown_complete() and time.monotonic() < deadline:
                time.sleep(0.01)
            wrapped = wait(active.get_result_async())
        finally:
            self.mocks.hold_speak = False
        self.assertTrue(self.executive.shutdown_complete())
        # The task execution callback drains before the five-second ros2 launch
        # grace period, leaving a separate bounded window for executor teardown.
        self.assertLess(time.monotonic() - started, 4.0)
        # Process shutdown requests a safe lower-action cancellation but is not
        # itself a client cancellation of ExecuteTask, so the enclosing action
        # remains an aborted transport result with a structured cancelled payload.
        self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
        self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_CANCELLED)

    def test_shutdown_keeps_unconfirmed_lower_action_owned_and_escalates(self):
        """Process shutdown never reports full drain while a lower action is live."""
        lower_goal = FakeLowerGoal(cancel_timeout_attempts=10)
        submission = Future()
        submission.set_result(lower_goal)
        self.safety_probe.reset_observation()
        with patch.object(
                self.executive._navigate_client, 'send_goal_async',
                return_value=submission):
            active = self._send(self._plan('navigate_to', 'location', 'kitchen'))
            time.sleep(0.05)
            self.executive.request_shutdown()
            wrapped = wait(active.get_result_async())

        self.assertEqual(wrapped.status, GoalStatus.STATUS_ABORTED)
        self.assertEqual(wrapped.result.outcome, ExecuteTask.Result.OUTCOME_FAILED)
        self.assertFalse(self.executive.shutdown_complete())
        self.assertTrue(self.safety_probe.event.wait(1.0))
        self.assertEqual(
            self.safety_probe.request.reason_code,
            EmergencyStopRequest.REASON_SYSTEM_FAULT)
        self.assertFalse(self.safety_probe.motion_permitted)
        self.assertEqual(self.safety_probe.safe_linear_velocity, 0.0)

        terminal = NavigateToNamedLocation.Result()
        terminal.outcome = NavigateToNamedLocation.Result.OUTCOME_CANCELLED
        lower_goal._result.set_result(SimpleNamespace(
            status=GoalStatus.STATUS_CANCELED, result=terminal))
        self._wait_for_quarantine_release()
        self.assertTrue(self.executive.shutdown_complete())

    def test_shutdown_deadline_escalates_an_inflight_lower_action_before_teardown(self):
        """The final bounded-teardown report cannot silently drop ownership."""
        lower_goal = FakeLowerGoal()
        self.executive._set_active_lower_goal(lower_goal, lower_goal.get_result_async())
        self.safety_probe.reset_observation()
        self.executive._report_unresolved_lower_shutdown('bounded shutdown deadline expired')

        self.assertTrue(self.safety_probe.event.wait(1.0))
        self.assertEqual(
            self.safety_probe.request.reason_code,
            EmergencyStopRequest.REASON_SYSTEM_FAULT)
        with self.executive._lock:
            self.assertIs(self.executive._quarantined_lower_goal, lower_goal)
        terminal = Speak.Result()
        terminal.outcome = Speak.Result.OUTCOME_CANCELLED
        lower_goal._result.set_result(SimpleNamespace(
            status=GoalStatus.STATUS_CANCELED, result=terminal))
        self._wait_for_quarantine_release()
        with self.executive._lock:
            self.executive._active_lower_goal = None
            self.executive._active_lower_result = None

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
