"""Frozen, machine-readable schemas for Buddy's initial capabilities."""

from dataclasses import dataclass
from math import isfinite


ERROR_INVALID_ARGUMENTS = 3001
ERROR_UNKNOWN_CAPABILITY = 3002
ERROR_CAPABILITY_UNAVAILABLE = 3003
ERROR_PRECONDITION = 3004
ERROR_TIMEOUT = 3005
ERROR_CONFIRMATION_REQUIRED = 3006
ERROR_INVALID_PLAN = 3007


@dataclass(frozen=True)
class ArgumentSchema:
    """The accepted representation of one task argument."""

    name: str
    value_type: int
    required: bool
    description: str
    default_value: str = ''
    allowed_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilitySchema:
    """An initial capability and its static policy requirements."""

    name: str
    description: str
    arguments: tuple[ArgumentSchema, ...]
    requires_motion: bool
    requires_localization: bool
    requires_confirmation: bool


class ArgumentValidationError(ValueError):
    """Validation failure carrying the frozen task/capability error code."""

    def __init__(self, message: str, code: int = ERROR_INVALID_ARGUMENTS):
        super().__init__(message)
        self.code = code


# Numeric constants are deliberately duplicated here rather than importing a
# generated ROS class: this module remains deterministic and unit-testable.
TYPE_STRING = 0
TYPE_INTEGER = 1
TYPE_FLOAT = 2
TYPE_BOOLEAN = 3

CAPABILITIES = (
    CapabilitySchema('stop', 'Cancel active motion and request a soft stop.', (),
                     False, False, False),
    CapabilitySchema('speak', 'Speak supplied text through the voice action.', (
        ArgumentSchema('text', TYPE_STRING, True, 'Text to speak.'),
        ArgumentSchema('voice', TYPE_STRING, False, 'Optional voice name.'),
    ), False, False, False),
    CapabilitySchema('navigate_to', 'Navigate to a configured named location.', (
        ArgumentSchema('location', TYPE_STRING, True, 'Configured location name.'),
    ), True, True, True),
    CapabilitySchema('report_status', 'Report the latest robot status summary.', (),
                     False, False, False),
)

CAPABILITY_BY_NAME = {capability.name: capability for capability in CAPABILITIES}


def schema_for(name: str) -> CapabilitySchema:
    """Return a known schema or fail with the assigned unknown-capability code."""
    try:
        return CAPABILITY_BY_NAME[name]
    except KeyError as error:
        raise ArgumentValidationError(
            'unknown capability: ' + name, ERROR_UNKNOWN_CAPABILITY) from error


def validate_arguments(schema: CapabilitySchema, arguments) -> dict[str, str]:
    """Reject duplicate, unknown, mistyped, missing, and malformed arguments."""
    expected = {argument.name: argument for argument in schema.arguments}
    values: dict[str, str] = {}
    for argument in arguments:
        if argument.name in values:
            raise ArgumentValidationError('duplicate argument: ' + argument.name)
        specification = expected.get(argument.name)
        if specification is None:
            raise ArgumentValidationError('unknown argument: ' + argument.name)
        if argument.value_type != specification.value_type:
            raise ArgumentValidationError('invalid type for argument: ' + argument.name)
        _validate_value(specification, argument.value)
        values[argument.name] = argument.value
    missing = [item.name for item in schema.arguments if item.required and item.name not in values]
    if missing:
        raise ArgumentValidationError('missing required argument: ' + missing[0])
    return values


def _validate_value(specification: ArgumentSchema, value: str) -> None:
    if specification.value_type == TYPE_STRING and not value:
        raise ArgumentValidationError('argument must not be empty: ' + specification.name)
    if specification.value_type == TYPE_INTEGER:
        try:
            int(value)
        except ValueError as error:
            raise ArgumentValidationError('invalid integer: ' + specification.name) from error
    if specification.value_type == TYPE_FLOAT:
        try:
            finite = isfinite(float(value))
        except ValueError as error:
            raise ArgumentValidationError('invalid float: ' + specification.name) from error
        if not finite:
            raise ArgumentValidationError('non-finite float: ' + specification.name)
    if specification.value_type == TYPE_BOOLEAN and value not in ('true', 'false'):
        raise ArgumentValidationError('invalid boolean: ' + specification.name)
    if specification.allowed_values and value not in specification.allowed_values:
        raise ArgumentValidationError('disallowed value: ' + specification.name)
