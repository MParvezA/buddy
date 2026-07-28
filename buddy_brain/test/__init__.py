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
    test_execute_result_requires_consistent_ros_and_custom_success,
    test_execute_result_true_success_and_transport_exception_are_deterministic,
    test_invalid_execute_goal_handle_is_structured_failure,
    test_node_construction_capability_refresh_confirmed_dispatch_and_motion_boundary,
)
from test.test_main_teardown import (
    test_entrypoint_static_shape_has_narrow_shutdown_handling,
    test_external_shutdown_does_not_request_a_second_shutdown,
    test_keyboard_interrupt_destroys_node_then_shuts_down_live_context,
    test_ordinary_runtime_exception_is_not_swallowed,
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
                test_execute_result_requires_consistent_ros_and_custom_success
            ),
            unittest.FunctionTestCase(
                test_execute_result_true_success_and_transport_exception_are_deterministic
            ),
            unittest.FunctionTestCase(
                test_invalid_execute_goal_handle_is_structured_failure
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
        ]
    )
