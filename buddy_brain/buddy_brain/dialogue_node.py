# Copyright 2026 SyncRobot

"""ROS adapter for the bounded dialogue state machine."""

from __future__ import annotations

import uuid
from typing import Any

import rclpy
from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Duration
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from buddy_interfaces.action import ExecuteTask, Speak
from buddy_interfaces.msg import (
    CapabilityArgument,
    RecognizedUtterance,
    RobotStatus,
    TaskArgument,
    TaskPlan,
    TaskStep,
    WorldSummary,
)
from buddy_interfaces.srv import ListCapabilities
from buddy_brain.dialogue_core import (
    ARGUMENT_TYPES,
    ArgumentSchema,
    CapabilitySchema,
    DialogueCore,
    DialogueEffect,
    ValidatedPlan,
)
from buddy_brain.model_provider import DeterministicFakeProvider


def _uuid_message(value: uuid.UUID) -> Any:
    """Populate a generated UUID message without accepting model-generated IDs."""
    from unique_identifier_msgs.msg import UUID

    message = UUID()
    message.uuid = list(value.bytes)
    return message


def _status_summary(message: RobotStatus) -> dict[str, Any]:
    return {
        "mode": message.mode,
        "localization_state": message.localization_state,
        "battery_percent": message.battery_percent,
        "battery_state_known": message.battery_state_known,
        "motion_ready": message.motion_ready,
        "current_location": message.current_location,
        "current_task": message.current_task,
    }


def _world_summary(message: WorldSummary) -> dict[str, Any]:
    """Retain semantic names only; pose geometry is deliberately not forwarded."""
    return {
        "robot_pose_valid": message.robot_pose_valid,
        "current_location": message.current_location,
        "named_locations": [location.name for location in message.named_locations if location.enabled],
        "objects": [observation.label for observation in message.objects],
    }


def _capability_schema(descriptor: Any) -> CapabilitySchema:
    type_names = {
        CapabilityArgument.TYPE_STRING: "string",
        CapabilityArgument.TYPE_INTEGER: "integer",
        CapabilityArgument.TYPE_FLOAT: "float",
        CapabilityArgument.TYPE_BOOLEAN: "boolean",
    }
    arguments = tuple(
        ArgumentSchema(
            argument.name,
            type_names.get(argument.value_type, "invalid"),
            argument.required,
            tuple(argument.allowed_values),
        )
        for argument in descriptor.arguments
    )
    if any(argument.value_type not in ARGUMENT_TYPES for argument in arguments):
        raise ValueError("capability service returned an unknown argument type")
    return CapabilitySchema(
        descriptor.name,
        descriptor.available,
        descriptor.requires_confirmation,
        arguments,
    )


class DialogueNode(Node):
    """Consumes bounded summaries and controls only the frozen task/speech actions."""

    def __init__(self) -> None:
        super().__init__("dialogue", namespace="/buddy")
        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", False)
        self.declare_parameter("fake_model_response", "")
        response = self.get_parameter("fake_model_response").value
        responses = [response] if isinstance(response, str) and response else None
        self._core = DialogueCore(DeterministicFakeProvider(responses))

        summary_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        utterance_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        diagnostics_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._utterance_subscription = self.create_subscription(
            RecognizedUtterance, "/buddy/voice/utterance", self._on_utterance, utterance_qos
        )
        self._status_subscription = self.create_subscription(
            RobotStatus, "/buddy/status", self._on_status, summary_qos
        )
        self._world_subscription = self.create_subscription(
            WorldSummary, "/buddy/world/summary", self._on_world, summary_qos
        )
        self._diagnostics_publisher = self.create_publisher(DiagnosticArray, "/diagnostics", diagnostics_qos)
        self._capabilities_client = self.create_client(ListCapabilities, "/buddy/capabilities/list")
        self._execute_client = ActionClient(self, ExecuteTask, "/buddy/tasks/execute")
        self._speak_client = ActionClient(self, Speak, "/buddy/voice/speak")
        self._capability_timer = self.create_timer(2.0, self._refresh_capabilities)
        self._diagnostic_timer = self.create_timer(5.0, self._publish_diagnostics)
        self._capabilities_in_flight = False

    def _on_status(self, message: RobotStatus) -> None:
        self._core.update_status(_status_summary(message))

    def _on_world(self, message: WorldSummary) -> None:
        self._core.update_world(_world_summary(message))

    def _on_utterance(self, message: RecognizedUtterance) -> None:
        if message.is_final:
            self._dispatch(self._core.receive_final_utterance(message.text))

    def _refresh_capabilities(self) -> None:
        if self._capabilities_in_flight or not self._capabilities_client.service_is_ready():
            return
        self._capabilities_in_flight = True
        future = self._capabilities_client.call_async(ListCapabilities.Request())
        future.add_done_callback(self._on_capabilities)

    def _on_capabilities(self, future: Any) -> None:
        self._capabilities_in_flight = False
        try:
            response = future.result()
            self._core.update_capabilities([_capability_schema(item) for item in response.capabilities])
        except Exception as exc:  # ROS service failures are reported diagnostically, not bypassed.
            self.get_logger().warning(f"capability refresh failed: {exc}")

    def _dispatch(self, effects: list[DialogueEffect]) -> None:
        for effect in effects:
            if effect.kind == "speak":
                self._request_speech(effect.text)
            elif effect.kind == "execute" and effect.plan is not None:
                self._execute(effect.plan)

    def _request_speech(self, text: str) -> None:
        if not self._speak_client.server_is_ready():
            self.get_logger().warning("speech action is unavailable")
            return
        goal = Speak.Goal()
        goal.request_id = _uuid_message(uuid.uuid4())
        goal.text = text
        goal.voice = ""
        goal.priority = 0
        goal.interrupt_current = False
        self._speak_client.send_goal_async(goal)

    def _execute(self, plan: ValidatedPlan) -> None:
        if not plan.user_confirmed:
            self.get_logger().error("refusing unconfirmed plan")
            return
        if not self._execute_client.server_is_ready():
            self._report_execution_result(
                "failed",
                "Task execution is unavailable.",
                DiagnosticStatus.ERROR,
                detail="task action server is unavailable",
            )
            return
        try:
            submission = self._execute_client.send_goal_async(self._to_execute_goal(plan))
            if submission is None or not callable(
                getattr(submission, "add_done_callback", None)
            ):
                self._report_execution_result(
                    "failed",
                    "Task execution could not be started.",
                    DiagnosticStatus.ERROR,
                    detail="task action returned an invalid submission future",
                )
                return
            submission.add_done_callback(self._on_execute_goal)
        except Exception as exc:
            self._report_execution_result(
                "failed",
                f"Task execution failed: {exc}",
                DiagnosticStatus.ERROR,
                detail="task goal submission raised an exception",
            )

    def _to_execute_goal(self, plan: ValidatedPlan) -> ExecuteTask.Goal:
        goal = ExecuteTask.Goal()
        task_plan = TaskPlan()
        task_plan.plan_id = _uuid_message(plan.plan_id)
        task_plan.session_id = _uuid_message(plan.session_id)
        task_plan.user_confirmed = plan.user_confirmed
        task_plan.summary = plan.summary
        for step in plan.steps:
            task_step = TaskStep()
            task_step.step_id = _uuid_message(step.step_id)
            task_step.capability = step.capability
            task_step.timeout = Duration(
                sec=int(step.timeout_seconds),
                nanosec=int((step.timeout_seconds % 1) * 1_000_000_000),
            )
            task_step.on_failure = (
                TaskStep.ON_FAILURE_ABORT if step.on_failure == "abort" else TaskStep.ON_FAILURE_CONTINUE
            )
            for argument in step.arguments:
                task_argument = TaskArgument()
                task_argument.name = argument.name
                task_argument.value_type = {
                    "string": TaskArgument.TYPE_STRING,
                    "integer": TaskArgument.TYPE_INTEGER,
                    "float": TaskArgument.TYPE_FLOAT,
                    "boolean": TaskArgument.TYPE_BOOLEAN,
                }[argument.value_type]
                task_argument.value = argument.value
                task_step.arguments.append(task_argument)
            task_plan.steps.append(task_step)
        goal.plan = task_plan
        return goal

    def _on_execute_goal(self, future: Any) -> None:
        try:
            goal_handle = future.result()
            handle_has_acceptance = (
                goal_handle is not None and hasattr(goal_handle, "accepted")
            )
            result_method = getattr(goal_handle, "get_result_async", None)
            handle_has_result = callable(result_method)
            if not handle_has_acceptance or not handle_has_result:
                self._report_execution_result(
                    "failed",
                    "Task execution could not be started.",
                    DiagnosticStatus.ERROR,
                    detail="task action returned an invalid goal handle",
                )
                return
            if not goal_handle.accepted:
                self._report_execution_result(
                    "rejected",
                    "The task was rejected.",
                    DiagnosticStatus.WARN,
                    detail="task goal was rejected",
                )
                return
            result_future = goal_handle.get_result_async()
            if result_future is None or not callable(
                getattr(result_future, "add_done_callback", None)
            ):
                self._report_execution_result(
                    "failed",
                    "Task execution failed.",
                    DiagnosticStatus.ERROR,
                    detail="task action returned an invalid result future",
                )
                return
            result_future.add_done_callback(self._on_execute_result)
        except Exception as exc:
            self._report_execution_result(
                "failed",
                f"Task execution failed: {exc}",
                DiagnosticStatus.ERROR,
                detail="task goal submission future failed",
            )

    def _on_execute_result(self, future: Any) -> None:
        try:
            wrapped = future.result()
            result = wrapped.result
            status = wrapped.status
            custom_outcome = result.outcome
            transport_succeeded = status == GoalStatus.STATUS_SUCCEEDED
            custom_succeeded = (
                custom_outcome == ExecuteTask.Result.OUTCOME_SUCCEEDED
            )
            if transport_succeeded and custom_succeeded:
                self._dispatch(
                    self._core.handle_execution_result("succeeded", result.message)
                )
                return
            transport_canceled = status == GoalStatus.STATUS_CANCELED
            custom_canceled = (
                custom_outcome == ExecuteTask.Result.OUTCOME_CANCELLED
            )
            if transport_canceled and custom_canceled:
                self._report_execution_result(
                    "canceled",
                    "The task was canceled.",
                    DiagnosticStatus.WARN,
                    status=status,
                    custom_outcome=custom_outcome,
                    detail="task action reached the canceled terminal state",
                )
                return
            if status == GoalStatus.STATUS_ABORTED:
                message = "Task execution failed."
                detail = "task action reached the aborted terminal state"
            elif status not in (
                GoalStatus.STATUS_SUCCEEDED,
                GoalStatus.STATUS_CANCELED,
                GoalStatus.STATUS_ABORTED,
            ):
                message = "Task execution returned an unknown status."
                detail = "task action returned non-terminal or invalid status"
            else:
                message = "Task execution returned an inconsistent result."
                detail = "task action status and custom outcome disagreed"
            self._report_execution_result(
                "failed",
                message,
                DiagnosticStatus.ERROR,
                status=status,
                custom_outcome=custom_outcome,
                detail=detail,
            )
        except Exception as exc:
            self._report_execution_result(
                "failed",
                f"Task execution failed: {exc}",
                DiagnosticStatus.ERROR,
                detail="task result future failed",
            )

    def _report_execution_result(
        self,
        outcome: str,
        user_message: str,
        level: int,
        *,
        status: int | None = None,
        custom_outcome: int | None = None,
        detail: str,
    ) -> None:
        log_message = detail
        if status is not None:
            log_message += f"; ROS status={_goal_status_name(status)}"
        if custom_outcome is not None:
            log_message += f"; custom outcome={custom_outcome}"
        if level == DiagnosticStatus.ERROR:
            self.get_logger().error(log_message)
        else:
            self.get_logger().warning(log_message)

        diagnostics = DiagnosticArray()
        diagnostics.header.stamp = self.get_clock().now().to_msg()
        diagnostic = DiagnosticStatus()
        diagnostic.name = "buddy_dialogue/execution"
        diagnostic.hardware_id = "buddy_brain"
        diagnostic.level = level
        diagnostic.message = user_message
        diagnostic.values = [
            KeyValue(key="detail", value=detail),
            KeyValue(
                key="ros_status",
                value="" if status is None else _goal_status_name(status),
            ),
            KeyValue(
                key="custom_outcome",
                value="" if custom_outcome is None else str(custom_outcome),
            ),
        ]
        diagnostics.status = [diagnostic]
        self._diagnostics_publisher.publish(diagnostics)
        self._dispatch(self._core.handle_execution_result(outcome, user_message))

    def _publish_diagnostics(self) -> None:
        diagnostics = DiagnosticArray()
        diagnostics.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = "buddy_dialogue"
        status.hardware_id = "buddy_brain"
        status.level = DiagnosticStatus.OK
        status.message = "bounded dialogue ready"
        status.values = [KeyValue(key="capability_source", value="/buddy/capabilities/list")]
        diagnostics.status = [status]
        self._diagnostics_publisher.publish(diagnostics)


def _goal_status_name(status: int) -> str:
    names = {
        GoalStatus.STATUS_UNKNOWN: "UNKNOWN",
        GoalStatus.STATUS_ACCEPTED: "ACCEPTED",
        GoalStatus.STATUS_EXECUTING: "EXECUTING",
        GoalStatus.STATUS_CANCELING: "CANCELING",
        GoalStatus.STATUS_SUCCEEDED: "SUCCEEDED",
        GoalStatus.STATUS_CANCELED: "CANCELED",
        GoalStatus.STATUS_ABORTED: "ABORTED",
    }
    return names.get(status, f"INVALID({status})")


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = DialogueNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
