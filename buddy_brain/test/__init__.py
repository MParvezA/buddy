# Copyright 2026 SyncRobot

"""Make the ament_python default unittest runner execute the pytest-style checks."""

import unittest

from test.test_dialogue_core import (
    test_clarification_cancellation_and_action_result_response,
    test_deterministic_provider_context_and_confirmation_gate_execution,
    test_malformed_hallucinated_and_wrong_type_model_output_is_rejected,
)
from test.test_package_boundary import (
    test_dialogue_package_has_no_motion_or_controller_boundary_violation,
)
from test.test_dialogue_node import (
    test_capability_service_loss_revokes_cached_dialogue_authorization,
    test_dialogue_health_waits_for_capabilities_and_action_servers,
    test_execute_result_requires_consistent_ros_and_custom_success,
    test_execute_result_true_success_and_transport_exception_are_deterministic,
    test_final_utterance_locale_selects_german_or_english_speak_voice,
    test_invalid_execute_goal_handle_is_structured_failure,
    test_node_construction_capability_refresh_confirmed_dispatch_and_motion_boundary,
    test_speech_action_rejection_and_terminal_outcomes_are_observed_without_recursion,
    test_speech_submission_and_result_transport_failures_are_diagnostic,
    test_provider_failure_publishes_diagnostic_and_never_dispatches_a_task,
    test_missing_explicit_provider_is_unready_and_never_dispatches_a_task,
)
from test.test_main_teardown import (
    test_entrypoint_static_shape_has_narrow_shutdown_handling,
    test_external_shutdown_does_not_request_a_second_shutdown,
    test_keyboard_interrupt_destroys_node_then_shuts_down_live_context,
    test_ordinary_runtime_exception_is_not_swallowed,
)
from test.test_llama_cpp_provider import (
    test_llama_cpp_config_requires_explicit_resources_and_profile_bounds,
    test_llama_cpp_crash_timeout_and_malformed_output_fail_closed_without_a_plan,
    test_llama_cpp_output_file_is_removed_after_every_terminal_path,
    test_llama_cpp_terminates_descendant_group_after_leader_exit,
    test_llama_cpp_shutdown_terminates_an_owned_child_process,
    test_llama_cpp_uses_argument_vector_and_extracts_one_framed_json_object,
    test_llama_cpp_reports_recovery_after_a_later_valid_completion,
    test_qwen_prompt_and_extraction_do_not_repair_schema_invalid_content,
)


def load_tests(loader, tests, pattern):
    del loader, tests, pattern
    return unittest.TestSuite(
        [
            unittest.FunctionTestCase(test_malformed_hallucinated_and_wrong_type_model_output_is_rejected),
            unittest.FunctionTestCase(test_deterministic_provider_context_and_confirmation_gate_execution),
            unittest.FunctionTestCase(test_clarification_cancellation_and_action_result_response),
            unittest.FunctionTestCase(test_dialogue_package_has_no_motion_or_controller_boundary_violation),
            unittest.FunctionTestCase(
                test_node_construction_capability_refresh_confirmed_dispatch_and_motion_boundary
            ),
            unittest.FunctionTestCase(
                test_dialogue_health_waits_for_capabilities_and_action_servers
            ),
            unittest.FunctionTestCase(
                test_capability_service_loss_revokes_cached_dialogue_authorization
            ),
            unittest.FunctionTestCase(
                test_execute_result_requires_consistent_ros_and_custom_success
            ),
            unittest.FunctionTestCase(
                test_execute_result_true_success_and_transport_exception_are_deterministic
            ),
            unittest.FunctionTestCase(
                test_invalid_execute_goal_handle_is_structured_failure
            ),
            unittest.FunctionTestCase(
                test_speech_action_rejection_and_terminal_outcomes_are_observed_without_recursion
            ),
            unittest.FunctionTestCase(
                test_speech_submission_and_result_transport_failures_are_diagnostic
            ),
            unittest.FunctionTestCase(
                test_final_utterance_locale_selects_german_or_english_speak_voice
            ),
            unittest.FunctionTestCase(
                test_provider_failure_publishes_diagnostic_and_never_dispatches_a_task
            ),
            unittest.FunctionTestCase(
                test_missing_explicit_provider_is_unready_and_never_dispatches_a_task
            ),
            unittest.FunctionTestCase(
                test_keyboard_interrupt_destroys_node_then_shuts_down_live_context
            ),
            unittest.FunctionTestCase(
                test_external_shutdown_does_not_request_a_second_shutdown
            ),
            unittest.FunctionTestCase(test_ordinary_runtime_exception_is_not_swallowed),
            unittest.FunctionTestCase(
                test_entrypoint_static_shape_has_narrow_shutdown_handling
            ),
            unittest.FunctionTestCase(
                test_llama_cpp_config_requires_explicit_resources_and_profile_bounds
            ),
            unittest.FunctionTestCase(
                test_llama_cpp_uses_argument_vector_and_extracts_one_framed_json_object
            ),
            unittest.FunctionTestCase(
                test_qwen_prompt_and_extraction_do_not_repair_schema_invalid_content
            ),
            unittest.FunctionTestCase(
                test_llama_cpp_crash_timeout_and_malformed_output_fail_closed_without_a_plan
            ),
            unittest.FunctionTestCase(test_llama_cpp_shutdown_terminates_an_owned_child_process),
            unittest.FunctionTestCase(
                test_llama_cpp_output_file_is_removed_after_every_terminal_path
            ),
            unittest.FunctionTestCase(
                test_llama_cpp_terminates_descendant_group_after_leader_exit
            ),
            unittest.FunctionTestCase(
                test_llama_cpp_reports_recovery_after_a_later_valid_completion
            ),
        ]
    )
