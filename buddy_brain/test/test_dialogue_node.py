# Copyright 2026 SyncRobot

"""Node-level checks using generated ROS messages and local fakes only."""

import os
import uuid

os.environ.setdefault("FASTDDS_BUILTIN_TRANSPORTS", "SHM")
os.environ.setdefault("ROS_LOG_DIR", "/tmp/buddy_brain_test_logs")

import rclpy

from buddy_brain.dialogue_core import DialogueEffect, ValidatedPlan
from buddy_brain.dialogue_node import DialogueNode
from buddy_interfaces.action import ExecuteTask
from buddy_interfaces.msg import CapabilityDescriptor


class _CapabilityFuture:

    def __init__(self, capabilities):
        self._capabilities = capabilities

    def result(self):
        return type("Response", (), {"capabilities": self._capabilities})()


class _ResultFuture:

    def __init__(self, result):
        self._result = result

    def result(self):
        return type("WrappedResult", (), {"result": self._result})()


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
        node._on_execute_result(_ResultFuture(action_result))
        assert responses[0].kind == "speak"
        assert responses[0].text == "Status reported."

        publisher_topics = [publisher.topic_name for publisher in node._publishers]
        assert all(not topic.startswith("/buddy/motion/") for topic in publisher_topics)
        assert "/diagnostics" in publisher_topics
    finally:
        node.destroy_node()
        rclpy.shutdown()
