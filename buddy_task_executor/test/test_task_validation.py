from types import SimpleNamespace
import unittest

from buddy_capabilities.catalog import ERROR_CONFIRMATION_REQUIRED, ERROR_TIMEOUT, TYPE_STRING
from buddy_task_executor.validation import validate_static_plan


def identifier(value):
    return SimpleNamespace(uuid=[value] * 16)


def step(identifier_value=2, capability='speak', arguments=None, timeout=5, on_failure=0):
    return SimpleNamespace(
        step_id=identifier(identifier_value), capability=capability,
        arguments=arguments if arguments is not None else [
            SimpleNamespace(name='text', value_type=TYPE_STRING, value='hello')],
        timeout=SimpleNamespace(sec=timeout, nanosec=0), on_failure=on_failure)


def plan(steps, confirmed=True, plan_identifier=1):
    return SimpleNamespace(
        plan_id=identifier(plan_identifier), session_id=identifier(9), steps=steps,
        user_confirmed=confirmed)


class TaskValidationTest(unittest.TestCase):

    def test_valid_plan_passes_static_validation(self):
        self.assertIsNone(validate_static_plan(plan([step()]), 20.0, 30.0))

    def test_rejects_zero_duplicate_and_unknown_ids_or_capabilities(self):
        zero = plan([step(identifier_value=0)])
        self.assertIn('step_id', validate_static_plan(zero, 20.0, 30.0).message)
        duplicate = plan([step(identifier_value=2), step(identifier_value=2)])
        self.assertIn('unique', validate_static_plan(duplicate, 20.0, 30.0).message)
        unknown = plan([step(capability='invented')])
        self.assertIn('unknown capability', validate_static_plan(unknown, 20.0, 30.0).message)

    def test_rejects_timeout_and_missing_confirmation_before_execution(self):
        timeout_failure = validate_static_plan(plan([step(timeout=21)]), 20.0, 30.0)
        self.assertEqual(timeout_failure.code, ERROR_TIMEOUT)
        navigation = step(
            capability='navigate_to',
            arguments=[SimpleNamespace(name='location', value_type=TYPE_STRING, value='kitchen')])
        confirmation_failure = validate_static_plan(
            plan([navigation], confirmed=False), 20.0, 30.0)
        self.assertEqual(confirmation_failure.code, ERROR_CONFIRMATION_REQUIRED)
