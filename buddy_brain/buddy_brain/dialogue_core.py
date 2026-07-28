# Copyright 2026 SyncRobot

"""Pure state machine for validating and confirming local-model task proposals."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from buddy_brain.model_provider import LocalModelProvider


ARGUMENT_TYPES = {"string", "integer", "float", "boolean"}


class ValidationError(ValueError):
    """A model proposal crossed a mandatory policy or schema boundary."""


@dataclass(frozen=True)
class ArgumentSchema:
    """One accepted argument for a registered capability."""

    name: str
    value_type: str
    required: bool
    allowed_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilitySchema:
    """A registered capability, received from the task executive."""

    name: str
    available: bool
    requires_confirmation: bool
    arguments: tuple[ArgumentSchema, ...]


@dataclass(frozen=True)
class ValidatedArgument:
    """A scalar value validated against a capability argument declaration."""

    name: str
    value_type: str
    value: str


@dataclass(frozen=True)
class ValidatedStep:
    """A single bounded, executable capability invocation."""

    capability: str
    arguments: tuple[ValidatedArgument, ...]
    timeout_seconds: float
    on_failure: str
    step_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(frozen=True)
class ValidatedPlan:
    """The only model-derived object permitted to reach task execution."""

    summary: str
    steps: tuple[ValidatedStep, ...]
    session_id: uuid.UUID
    user_confirmed: bool = False
    plan_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def confirmed(self) -> "ValidatedPlan":
        return ValidatedPlan(
            summary=self.summary,
            steps=self.steps,
            session_id=self.session_id,
            user_confirmed=True,
            plan_id=self.plan_id,
        )


@dataclass(frozen=True)
class DialogueEffect:
    """A side effect emitted by the pure state machine."""

    kind: str
    text: str = ""
    plan: ValidatedPlan | None = None


class ContextBuilder:
    """Builds an intentionally small context from frozen summary interfaces only."""

    @staticmethod
    def build(
        utterance: str,
        status: dict[str, Any] | None,
        world: dict[str, Any] | None,
        capabilities: dict[str, CapabilitySchema],
    ) -> str:
        status = status or {}
        world = world or {}
        payload = {
            "utterance": utterance,
            "robot_status": {
                "mode": status.get("mode"),
                "localization_state": status.get("localization_state"),
                "battery_percent": status.get("battery_percent"),
                "battery_state_known": status.get("battery_state_known"),
                "motion_ready": status.get("motion_ready"),
                "current_location": status.get("current_location"),
                "current_task": status.get("current_task"),
            },
            "world_summary": {
                "robot_pose_valid": world.get("robot_pose_valid"),
                "current_location": world.get("current_location"),
                "named_locations": list(world.get("named_locations", [])),
                "objects": list(world.get("objects", [])),
            },
            "registered_capabilities": [
                {
                    "name": schema.name,
                    "arguments": [
                        {"name": arg.name, "type": arg.value_type, "required": arg.required}
                        for arg in schema.arguments
                    ],
                }
                for schema in sorted(capabilities.values(), key=lambda item: item.name)
                if schema.available
            ],
            "response_schema": {
                "plan": {
                    "kind": "plan",
                    "summary": "string",
                    "steps": [
                        {
                            "capability": "registered capability name",
                            "arguments": "object of typed JSON scalars",
                            "timeout_seconds": "number from 1 to 300",
                            "on_failure": "abort or continue",
                        }
                    ],
                },
                "clarification": {"kind": "clarification", "question": "string"},
            },
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _canonical_scalar(value: Any, value_type: str) -> str:
    if value_type == "string" and isinstance(value, str):
        return value
    if value_type == "integer" and isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if value_type == "float" and isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(float(value))
    if value_type == "boolean" and isinstance(value, bool):
        return "true" if value else "false"
    raise ValidationError(f"argument has wrong type for {value_type}")


def validate_model_response(
    response_json: str,
    capabilities: dict[str, CapabilitySchema],
    session_id: uuid.UUID,
) -> str | ValidatedPlan:
    """Parse strict JSON and return only a clarification or validated task plan."""
    try:
        payload = json.loads(response_json)
    except json.JSONDecodeError as exc:
        raise ValidationError("model response is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) - {"kind", "question", "summary", "steps"}:
        raise ValidationError("model response has unknown fields")
    kind = payload.get("kind")
    if kind == "clarification":
        if set(payload) != {"kind", "question"} or not isinstance(payload["question"], str):
            raise ValidationError("clarification must contain one string question")
        question = payload["question"].strip()
        if not question:
            raise ValidationError("clarification question is empty")
        return question
    if kind != "plan" or set(payload) != {"kind", "summary", "steps"}:
        raise ValidationError("model response must be a plan or clarification")
    summary = payload["summary"]
    steps = payload["steps"]
    if not isinstance(summary, str) or not summary.strip() or not isinstance(steps, list) or not steps:
        raise ValidationError("plan requires a summary and at least one step")
    if len(steps) > 8:
        raise ValidationError("plan has too many steps")
    validated_steps: list[ValidatedStep] = []
    for step in steps:
        if not isinstance(step, dict) or set(step) != {
            "capability", "arguments", "timeout_seconds", "on_failure"
        }:
            raise ValidationError("step does not match the required schema")
        name = step["capability"]
        schema = capabilities.get(name) if isinstance(name, str) else None
        if schema is None or not schema.available:
            raise ValidationError("capability is not registered and available")
        if not isinstance(step["arguments"], dict):
            raise ValidationError("step arguments must be an object")
        supplied = step["arguments"]
        argument_schemas = {arg.name: arg for arg in schema.arguments}
        if set(supplied) - set(argument_schemas):
            raise ValidationError("step contains an unknown argument")
        arguments: list[ValidatedArgument] = []
        for argument in schema.arguments:
            if argument.required and argument.name not in supplied:
                raise ValidationError("step omits a required argument")
            if argument.name not in supplied:
                continue
            value = _canonical_scalar(supplied[argument.name], argument.value_type)
            if argument.allowed_values and value not in argument.allowed_values:
                raise ValidationError("argument value is not allowed")
            arguments.append(ValidatedArgument(argument.name, argument.value_type, value))
        timeout = step["timeout_seconds"]
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 1 <= timeout <= 300:
            raise ValidationError("timeout must be a number from 1 to 300 seconds")
        if step["on_failure"] not in {"abort", "continue"}:
            raise ValidationError("on_failure must be abort or continue")
        validated_steps.append(
            ValidatedStep(name, tuple(arguments), float(timeout), step["on_failure"])
        )
    return ValidatedPlan(summary.strip(), tuple(validated_steps), session_id)


class DialogueCore:
    """Holds confirmation state and never executes unconfirmed model output."""

    def __init__(self, provider: LocalModelProvider, session_id: uuid.UUID | None = None) -> None:
        self._provider = provider
        self._session_id = session_id or uuid.uuid4()
        self._capabilities: dict[str, CapabilitySchema] = {}
        self._status: dict[str, Any] | None = None
        self._world: dict[str, Any] | None = None
        self._pending: ValidatedPlan | None = None

    def update_capabilities(self, capabilities: list[CapabilitySchema]) -> None:
        self._capabilities = {capability.name: capability for capability in capabilities}

    def update_status(self, status: dict[str, Any]) -> None:
        self._status = dict(status)

    def update_world(self, world: dict[str, Any]) -> None:
        self._world = dict(world)

    def receive_final_utterance(self, text: str) -> list[DialogueEffect]:
        """Return speech and, only after a yes, an execute effect for one turn."""
        utterance = text.strip()
        if not utterance:
            return []
        if self._pending is not None:
            answer = utterance.casefold().strip(".!,?")
            if answer in {"yes", "confirm", "proceed"}:
                plan = self._pending.confirmed()
                self._pending = None
                return [DialogueEffect("execute", plan=plan)]
            if answer in {"no", "cancel", "don't", "do not"}:
                self._pending = None
                return [DialogueEffect("speak", "Okay, I will not execute that task.")]
            return [DialogueEffect("speak", "Please say yes to proceed or no to cancel.")]
        try:
            response = self._provider.complete(
                ContextBuilder.build(utterance, self._status, self._world, self._capabilities)
            )
            parsed = validate_model_response(response, self._capabilities, self._session_id)
        except (ValidationError, RuntimeError, ValueError):
            return [DialogueEffect("speak", "I could not safely form that task. Please rephrase it.")]
        if isinstance(parsed, str):
            return [DialogueEffect("speak", parsed)]
        self._pending = parsed
        return [DialogueEffect("speak", f"{parsed.summary}. Would you like me to proceed?")]

    def handle_execution_result(self, outcome: str, message: str) -> list[DialogueEffect]:
        """Convert an action result to an explicit, user-facing response."""
        if outcome == "succeeded":
            return [DialogueEffect("speak", message or "The task completed successfully.")]
        return [DialogueEffect("speak", message or "The task did not complete.")]
