# Copyright 2026 SyncRobot

import json
import uuid

from buddy_brain.dialogue_core import (
    ArgumentSchema,
    CapabilitySchema,
    DialogueCore,
    ValidationError,
    validate_model_response,
)
from buddy_brain.model_provider import DeterministicFakeProvider


def _capabilities():
    return [
        CapabilitySchema(
            "navigate_to",
            True,
            True,
            (ArgumentSchema("location", "string", True),),
        ),
        CapabilitySchema("report_status", True, False, ()),
    ]


def _valid_plan():
    return json.dumps(
        {
            "kind": "plan",
            "summary": "I will go to the kitchen",
            "steps": [
                {
                    "capability": "navigate_to",
                    "arguments": {"location": "kitchen"},
                    "timeout_seconds": 30,
                    "on_failure": "abort",
                }
            ],
        }
    )


def test_malformed_hallucinated_and_wrong_type_model_output_is_rejected():
    capabilities = {item.name: item for item in _capabilities()}
    for response in [
        "not json",
        _valid_plan().replace("navigate_to", "drive_anywhere"),
        _valid_plan().replace('"kitchen"', "42"),
    ]:
        try:
            validate_model_response(response, capabilities, uuid.uuid4())
        except ValidationError:
            pass
        else:
            raise AssertionError("unsafe model output was accepted")


def test_deterministic_provider_context_and_confirmation_gate_execution():
    provider = DeterministicFakeProvider([_valid_plan()])
    core = DialogueCore(provider, session_id=uuid.UUID(int=7))
    core.update_capabilities(_capabilities())
    core.update_status({"mode": 1, "current_location": "hall", "motion_ready": True})
    core.update_world({"current_location": "hall", "named_locations": ["kitchen"]})

    proposal = core.receive_final_utterance("take me to the kitchen")
    assert proposal[0].kind == "speak"
    assert "Would you like me to proceed?" in proposal[0].text
    assert len(provider.contexts) == 1
    context = json.loads(provider.contexts[0])
    assert context["world_summary"]["named_locations"] == ["kitchen"]
    assert '"robot_pose":' not in provider.contexts[0]

    assert core.receive_final_utterance("maybe")[0].kind == "speak"
    execution = core.receive_final_utterance("yes")
    assert len(execution) == 1
    assert execution[0].kind == "execute"
    assert execution[0].plan.user_confirmed is True


def test_clarification_cancellation_and_action_result_response():
    provider = DeterministicFakeProvider(
        ['{"kind":"clarification","question":"Which room should I use?"}', _valid_plan()]
    )
    core = DialogueCore(provider)
    core.update_capabilities(_capabilities())
    assert core.receive_final_utterance("go somewhere")[0].text == "Which room should I use?"
    assert "Would you like" in core.receive_final_utterance("go to kitchen")[0].text
    assert "will not execute" in core.receive_final_utterance("no")[0].text
    assert core.handle_execution_result("succeeded", "Arrived in the kitchen.")[0].text == "Arrived in the kitchen."
    assert core.handle_execution_result("failed", "Navigation failed.")[0].text == "Navigation failed."
