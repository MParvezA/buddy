from types import SimpleNamespace
import unittest

from buddy_capabilities.catalog import (
    ArgumentValidationError, CAPABILITY_BY_NAME, ERROR_UNKNOWN_CAPABILITY,
    schema_for, TYPE_BOOLEAN, TYPE_STRING, validate_arguments)


def argument(name, value_type, value):
    return SimpleNamespace(name=name, value_type=value_type, value=value)


class CatalogTest(unittest.TestCase):

    def test_initial_catalogue_has_exact_capability_names(self):
        self.assertEqual(
            list(CAPABILITY_BY_NAME), ['stop', 'speak', 'navigate_to', 'report_status'])

    def test_rejects_unknown_duplicate_and_missing_arguments(self):
        speak = schema_for('speak')
        with self.assertRaisesRegex(ArgumentValidationError, 'missing'):
            validate_arguments(speak, [])
        with self.assertRaisesRegex(ArgumentValidationError, 'duplicate'):
            validate_arguments(speak, [argument('text', TYPE_STRING, 'one'),
                                       argument('text', TYPE_STRING, 'two')])
        with self.assertRaisesRegex(ArgumentValidationError, 'unknown'):
            validate_arguments(speak, [argument('unknown', TYPE_STRING, 'one'),
                                       argument('text', TYPE_STRING, 'two')])

    def test_rejects_invalid_typed_values_and_unknown_capability(self):
        with self.assertRaisesRegex(ArgumentValidationError, 'invalid type'):
            validate_arguments(schema_for('speak'), [argument('text', TYPE_BOOLEAN, 'true')])
        with self.assertRaises(ArgumentValidationError) as error:
            schema_for('not_registered')
        self.assertEqual(error.exception.code, ERROR_UNKNOWN_CAPABILITY)
