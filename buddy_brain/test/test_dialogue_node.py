# Copyright 2026 SyncRobot

"""Node-level checks using generated ROS messages and local fakes only."""

import os
import uuid

os.environ.setdefault("FASTDDS_BUILTIN_TRANSPORTS", "SHM")
os.environ.setdefault("ROS_LOG_DIR", "/tmp/buddy_brain_test_logs")

import rclpy

from action_msgs.msg import GoalStatus
from buddy_brain.dialogue_core import DialogueEffect, ValidatedPlan
from buddy_brain.dialogue_node import DialogueNode
from buddy_interfaces.action import ExecuteTask, Speak
from buddy_interfaces.msg import CapabilityDescriptor


class _CapabilityFuture:

    def __init__(self, capabilities):
        self._capabilities = capabilities

    def result(self):
        return type("Response", (), {"capabilities": self._capabilities})()


class _ResultFuture:

    def __init__(self, result=None, status=GoalStatus.STATUS_SUCCEEDED, error=None):
        self._result = result
        self._status = status
        self._error = error

    def result(self):
        if self._error is not None:
            raise self._error
        return type(
            "WrappedResult",
            (),
            {"result": self._result, "status": self._status},
        )()


class _GoalFuture:

    def __init__(self, goal_handle):
        self._goal_handle = goal_handle

    def result(self):
        return self._goal_handle


class _DoneCallbackFuture:

    def __init__(self, value):
        self._value = value

    def result(self):
        return self._value

    def add_done_callback(self, callback):
        callback(self)


class _SpeechClient:

    def __init__(self, submission=None, error=None, ready=True):
        self._submission = submission
        self._error = error
        self._ready = ready
        self.goals = []

    def server_is_ready(self):
        return self._ready

    def send_goal_async(self, goal):
        self.goals.append(goal)
        if self._error is not None:
            raise self._error
        return self._submission


class _ReadinessClient:

    def __init__(self, ready):
        self._ready = ready

    def server_is_ready(self):
        return self._ready

    def service_is_ready(self):
        return self._ready


class _RejectedGoal:

    accepted = False

    @staticmethod
    def get_result_async():
        raise AssertionError("rejected goal must not request a result")


class _DiagnosticSink:

    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


def _result_effect(node, status, custom_outcome, message=""):
    action_result = ExecuteTask.Result()
    action_result.outcome = custom_outcome
    action_result.message = message
    responses = []
    node._dispatch = responses.extend
    node._on_execute_result(_ResultFuture(action_result, status))
    return responses[0]


def _speech_result(node, status, custom_outcome, message=""):
    action_result = Speak.Result()
    action_result.outcome = custom_outcome
    action_result.message = message
    node._on_speak_result(_ResultFuture(action_result, status))


def test_node_construction_capability_refresh_confirmed_dispatch_and_motion_boundary():
    """Exercise the ROS adapter without a task, voice, or motion neighbor."""
    rclpy.init()
    node = DialogueNode()
    try:
        descriptor = CapabilityDescriptor()
        descriptor.name = "report_status"
        descriptor.available = True
        descriptor.requires_confirmation = False
        node._on_capabilities(_CapabilityFuture([descriptor]))
        assert node._core._capabilities["report_status"].arguments == ()
        assert node.has_parameter("use_sim_time")

        dispatched = []
        node._execute = dispatched.append
        plan = ValidatedPlan("Report status", (), uuid.uuid4(), user_confirmed=True)
        node._dispatch([DialogueEffect("execute", plan=plan)])
        assert dispatched == [plan]

        action_result = ExecuteTask.Result()
        action_result.outcome = ExecuteTask.Result.OUTCOME_SUCCEEDED
        action_result.message = "Status reported."
        responses = []
        node._dispatch = responses.extend
        node._on_execute_result(
            _ResultFuture(action_result, GoalStatus.STATUS_SUCCEEDED))
        assert responses[0].kind == "speak"
        assert responses[0].text == "Status reported."

        publisher_topics = [publisher.topic_name for publisher in node._publishers]
        assert all(not topic.startswith("/buddy/motion/") for topic in publisher_topics)
        assert "/diagnostics" in publisher_topics
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_execute_result_requires_consistent_ros_and_custom_success():
    rclpy.init()
    node = DialogueNode()
    publisher = node._diagnostics_publisher
    diagnostics = _DiagnosticSink()
    node._diagnostics_publisher = diagnostics
    try:
        cases = (
            (
                GoalStatus.STATUS_ABORTED,
                ExecuteTask.Result.OUTCOME_SUCCEEDED,
                "Task execution failed.",
            ),
            (
                GoalStatus.STATUS_CANCELED,
                ExecuteTask.Result.OUTCOME_CANCELLED,
                "The task was canceled.",
            ),
            (
                GoalStatus.STATUS_UNKNOWN,
                ExecuteTask.Result.OUTCOME_SUCCEEDED,
                "Task execution returned an unknown status.",
            ),
            (
                255,
                ExecuteTask.Result.OUTCOME_SUCCEEDED,
                "Task execution returned an unknown status.",
            ),
            (
                GoalStatus.STATUS_SUCCEEDED,
                ExecuteTask.Result.OUTCOME_FAILED,
                "Task execution returned an inconsistent result.",
            ),
        )
        for status, custom_outcome, expected in cases:
            effect = _result_effect(
                node, status, custom_outcome, "unsafe success text")
            assert effect.kind == "speak"
            assert effect.text == expected
            assert "success" not in effect.text.lower()
            diagnostic = diagnostics.messages[-1].status[0]
            assert diagnostic.message == expected
            expected_level = (
                diagnostic.WARN
                if status == GoalStatus.STATUS_CANCELED
                else diagnostic.ERROR
            )
            assert diagnostic.level == expected_level
    finally:
        node._diagnostics_publisher = publisher
        node.destroy_node()
        rclpy.shutdown()


def test_execute_result_true_success_and_transport_exception_are_deterministic():
    rclpy.init()
    node = DialogueNode()
    publisher = node._diagnostics_publisher
    diagnostics = _DiagnosticSink()
    node._diagnostics_publisher = diagnostics
    try:
        succeeded = _result_effect(
            node,
            GoalStatus.STATUS_SUCCEEDED,
            ExecuteTask.Result.OUTCOME_SUCCEEDED,
            "Task completed.",
        )
        assert succeeded.text == "Task completed."
        assert diagnostics.messages == []

        responses = []
        node._dispatch = responses.extend
        node._on_execute_result(
            _ResultFuture(error=RuntimeError("result transport failed")))
        assert responses[0].text == "Task execution failed: result transport failed"
        assert "success" not in responses[0].text.lower()
        diagnostic = diagnostics.messages[-1].status[0]
        assert diagnostic.level == diagnostic.ERROR
        assert diagnostic.message == responses[0].text

        responses.clear()
        node._on_execute_goal(_GoalFuture(_RejectedGoal()))
        assert responses[0].text == "The task was rejected."
        assert diagnostics.messages[-1].status[0].level == diagnostic.WARN
    finally:
        node._diagnostics_publisher = publisher
        node.destroy_node()
        rclpy.shutdown()


def test_invalid_execute_goal_handle_is_structured_failure():
    rclpy.init()
    node = DialogueNode()
    publisher = node._diagnostics_publisher
    diagnostics = _DiagnosticSink()
    node._diagnostics_publisher = diagnostics
    try:
        responses = []
        node._dispatch = responses.extend
        node._on_execute_goal(_GoalFuture(None))
        assert responses[0].kind == "speak"
        assert responses[0].text == "Task execution could not be started."
        assert "success" not in responses[0].text.lower()
        diagnostic = diagnostics.messages[-1].status[0]
        assert diagnostic.level == diagnostic.ERROR
        assert diagnostic.message == responses[0].text
    finally:
        node._diagnostics_publisher = publisher
        node.destroy_node()
        rclpy.shutdown()


def test_speech_action_rejection_and_terminal_outcomes_are_observed_without_recursion():
    rclpy.init()
    node = DialogueNode()
    publisher = node._diagnostics_publisher
    diagnostics = _DiagnosticSink()
    node._diagnostics_publisher = diagnostics
    dispatched = []
    node._dispatch = dispatched.extend
    try:
        node._on_speak_goal(_GoalFuture(_RejectedGoal()))
        rejected = diagnostics.messages[-1].status[0]
        assert rejected.name == "buddy_dialogue/speech"
        assert rejected.level == rejected.WARN
        assert rejected.message == "Speech request was rejected."

        _speech_result(
            node,
            GoalStatus.STATUS_ABORTED,
            Speak.Result.OUTCOME_SUCCEEDED,
            "default-success payload must not override an aborted action",
        )
        aborted = diagnostics.messages[-1].status[0]
        assert aborted.level == aborted.ERROR
        assert aborted.message == "Speech request failed."
        assert {value.key: value.value for value in aborted.values}["ros_status"] == "ABORTED"

        _speech_result(
            node,
            GoalStatus.STATUS_SUCCEEDED,
            Speak.Result.OUTCOME_FAILED,
            "custom failure",
        )
        custom_failure = diagnostics.messages[-1].status[0]
        assert custom_failure.level == custom_failure.ERROR
        assert custom_failure.message == "Speech request returned an inconsistent result."

        count_before_success = len(diagnostics.messages)
        _speech_result(
            node,
            GoalStatus.STATUS_SUCCEEDED,
            Speak.Result.OUTCOME_SUCCEEDED,
            "spoken",
        )
        assert len(diagnostics.messages) == count_before_success
        assert dispatched == []
    finally:
        node._diagnostics_publisher = publisher
        node.destroy_node()
        rclpy.shutdown()


def test_speech_submission_and_result_transport_failures_are_diagnostic():
    rclpy.init()
    node = DialogueNode()
    publisher = node._diagnostics_publisher
    diagnostics = _DiagnosticSink()
    node._diagnostics_publisher = diagnostics
    original_client = node._speak_client
    try:
        node._speak_client = _SpeechClient(error=RuntimeError("submission transport failed"))
        node._request_speech("hello")
        submission_failure = diagnostics.messages[-1].status[0]
        assert submission_failure.level == submission_failure.ERROR
        assert submission_failure.message == "Speech request failed: submission transport failed"

        node._on_speak_result(_ResultFuture(error=RuntimeError("result transport failed")))
        result_failure = diagnostics.messages[-1].status[0]
        assert result_failure.level == result_failure.ERROR
        assert result_failure.message == "Speech request failed: result transport failed"

        rejected_submission = _DoneCallbackFuture(_RejectedGoal())
        node._speak_client = _SpeechClient(submission=rejected_submission)
        node._request_speech("hello")
        rejected = diagnostics.messages[-1].status[0]
        assert rejected.message == "Speech request was rejected."
        assert node._speak_client.goals[0].text == "hello"
    finally:
        node._speak_client = original_client
        node._diagnostics_publisher = publisher
        node.destroy_node()
        rclpy.shutdown()


def test_dialogue_health_waits_for_capabilities_and_action_servers():
    rclpy.init()
    node = DialogueNode()
    publisher = node._diagnostics_publisher
    diagnostics = _DiagnosticSink()
    original_execute_client = node._execute_client
    original_speak_client = node._speak_client
    node._diagnostics_publisher = diagnostics
    try:
        node._execute_client = _ReadinessClient(False)
        node._speak_client = _ReadinessClient(False)
        node._publish_diagnostics()
        waiting = diagnostics.messages[-1].status[0]
        waiting_values = {value.key: value.value for value in waiting.values}
        assert waiting.name == "buddy_dialogue"
        assert waiting.level == waiting.WARN
        assert waiting.message == "waiting for dialogue dependencies"
        assert waiting_values == {
            "capabilities_ready": "false",
            "capability_count": "0",
            "task_executor_ready": "false",
            "speech_ready": "false",
        }

        descriptor = CapabilityDescriptor()
        descriptor.name = "report_status"
        descriptor.available = True
        descriptor.requires_confirmation = False
        node._on_capabilities(_CapabilityFuture([descriptor]))
        node._execute_client = _ReadinessClient(True)
        node._speak_client = _ReadinessClient(True)
        node._publish_diagnostics()
        ready = diagnostics.messages[-1].status[0]
        ready_values = {value.key: value.value for value in ready.values}
        assert ready.level == ready.OK
        assert ready.message == "bounded dialogue ready"
        assert ready_values == {
            "capabilities_ready": "true",
            "capability_count": "1",
            "task_executor_ready": "true",
            "speech_ready": "true",
        }
    finally:
        node._execute_client = original_execute_client
        node._speak_client = original_speak_client
        node._diagnostics_publisher = publisher
        node.destroy_node()
        rclpy.shutdown()


def test_capability_service_loss_revokes_cached_dialogue_authorization():
    rclpy.init()
    node = DialogueNode()
    original_capabilities_client = node._capabilities_client
    try:
        descriptor = CapabilityDescriptor()
        descriptor.name = "report_status"
        descriptor.available = True
        descriptor.requires_confirmation = False
        node._on_capabilities(_CapabilityFuture([descriptor]))
        assert node._capabilities_ready
        assert node._capability_count == 1
        assert "report_status" in node._core._capabilities

        node._capabilities_client = _ReadinessClient(False)
        node._refresh_capabilities()

        assert not node._capabilities_ready
        assert node._capability_count == 0
        assert node._core._capabilities == {}
    finally:
        node._capabilities_client = original_capabilities_client
        node.destroy_node()
        rclpy.shutdown()
