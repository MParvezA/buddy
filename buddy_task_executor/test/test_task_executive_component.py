"""Component tests keep task execution isolated from neighbor implementations."""

import os
from test.mock_action_servers import MockCapabilityActionServers
import threading
import time
import unittest

from buddy_capabilities.catalog import TYPE_STRING
from buddy_interfaces.action import ExecuteTask, NavigateToNamedLocation
from buddy_interfaces.msg import (
    NamedLocation, RobotStatus, SafetyState, TaskArgument, TaskPlan, TaskStep,
    WorldSummary)
from buddy_task_executor.executive import TaskExecutive
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


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


class TaskExecutiveComponentTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('ROS_LOG_DIR', '/tmp')
        os.environ.setdefault('FASTDDS_BUILTIN_TRANSPORTS', 'SHM')
        rclpy.init()
        cls.executive = TaskExecutive()
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
        goal = ExecuteTask.Goal()
        goal.plan = plan
        goal_handle = wait(self.client.send_goal_async(goal))
        self.assertTrue(goal_handle.accepted)
        return wait(goal_handle.get_result_async()).result

    def _send(self, plan, feedback_callback=None):
        goal = ExecuteTask.Goal()
        goal.plan = plan
        return wait(self.client.send_goal_async(goal, feedback_callback=feedback_callback))

    def test_executes_speak_through_deterministic_mock_action(self):
        result = self._result(self._plan('speak'))
        self.assertEqual(result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)
        self.assertEqual(result.step_results[0].outcome, 0)
        self.assertEqual(self.mocks.speak_requests[-1].text, 'hello')

    def test_unknown_capability_returns_structured_rejection_without_side_effect(self):
        before = len(self.mocks.speak_requests)
        result = self._result(self._plan('not_registered', argument_name=''))
        self.assertEqual(result.outcome, ExecuteTask.Result.OUTCOME_REJECTED)
        self.assertEqual(result.step_results[0].outcome, 2)
        self.assertEqual(len(self.mocks.speak_requests), before)

    def test_speak_timeout_cancels_mock_action_and_returns_timed_out_step(self):
        self.mocks.hold_speak = True
        try:
            result = self._result(self._plan('speak', timeout=1))
        finally:
            self.mocks.hold_speak = False
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
            result = wait(goal_handle.get_result_async()).result
        finally:
            self.mocks.hold_speak = False
        self.assertEqual(result.outcome, ExecuteTask.Result.OUTCOME_CANCELLED)
        self.assertIn(ExecuteTask.Feedback.STATE_EXECUTING, feedback)

    def test_registered_stop_cancels_an_active_task(self):
        self.mocks.hold_speak = True
        try:
            active = self._send(self._plan('speak'))
            time.sleep(0.1)
            stop_result = self._result(self._plan('stop', argument_name=''))
            active_result = wait(active.get_result_async()).result
        finally:
            self.mocks.hold_speak = False
        self.assertEqual(stop_result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)
        self.assertEqual(active_result.outcome, ExecuteTask.Result.OUTCOME_CANCELLED)

    def test_stop_waits_for_active_speech_cancellation(self):
        self.mocks.hold_speak = True
        try:
            active = self._send(self._plan('speak'))
            time.sleep(0.1)
            stop_result = self._result(self._plan('stop', argument_name=''))
            active_result = wait(active.get_result_async()).result
        finally:
            self.mocks.hold_speak = False
        self.assertEqual(stop_result.outcome, ExecuteTask.Result.OUTCOME_SUCCEEDED)
        self.assertEqual(active_result.outcome, ExecuteTask.Result.OUTCOME_CANCELLED)

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
