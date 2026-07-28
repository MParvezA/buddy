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
    test_node_construction_capability_refresh_confirmed_dispatch_and_motion_boundary,
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
        ]
    )
