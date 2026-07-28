"""Pure task-plan validation shared by the action server and unit tests."""

from dataclasses import dataclass

from buddy_capabilities.catalog import (
    ArgumentValidationError, ERROR_CONFIRMATION_REQUIRED, ERROR_INVALID_PLAN,
    ERROR_TIMEOUT, schema_for, validate_arguments)


@dataclass(frozen=True)
class ValidationFailure:
    """A non-executable task plan reason with an optional failed step index."""

    code: int
    message: str
    step_index: int | None = None


def duration_seconds(duration) -> float:
    """Convert the frozen Duration shape without accepting negative components."""
    if duration.sec < 0 or duration.nanosec < 0 or duration.nanosec >= 1000000000:
        return -1.0
    return float(duration.sec) + float(duration.nanosec) / 1000000000.0


def uuid_is_zero(identifier) -> bool:
    """Treat malformed UUIDs as zero IDs, rather than accepting them accidentally."""
    return len(identifier.uuid) != 16 or all(value == 0 for value in identifier.uuid)


def validate_static_plan(plan, max_step_timeout: float, max_overall_timeout: float):
    """Validate all frozen plan syntax before any side effect can start."""
    if uuid_is_zero(plan.plan_id):
        return ValidationFailure(ERROR_INVALID_PLAN, 'plan_id must be a non-zero UUID')
    if uuid_is_zero(plan.session_id):
        return ValidationFailure(ERROR_INVALID_PLAN, 'session_id must be a non-zero UUID')
    if not plan.steps:
        return ValidationFailure(ERROR_INVALID_PLAN, 'plan must contain at least one step')
    seen = set()
    total_timeout = 0.0
    for index, step in enumerate(plan.steps):
        if uuid_is_zero(step.step_id):
            return ValidationFailure(ERROR_INVALID_PLAN, 'step_id must be a non-zero UUID', index)
        key = tuple(step.step_id.uuid)
        if key in seen:
            return ValidationFailure(ERROR_INVALID_PLAN, 'step_id values must be unique', index)
        seen.add(key)
        timeout = duration_seconds(step.timeout)
        if timeout <= 0.0 or timeout > max_step_timeout:
            return ValidationFailure(
                ERROR_TIMEOUT, 'step timeout is outside configured bounds', index)
        total_timeout += timeout
        if total_timeout > max_overall_timeout:
            return ValidationFailure(ERROR_TIMEOUT, 'plan timeout exceeds configured bound', index)
        if step.on_failure not in (0, 1):
            return ValidationFailure(ERROR_INVALID_PLAN, 'invalid on_failure policy', index)
        try:
            schema = schema_for(step.capability)
            validate_arguments(schema, step.arguments)
        except ArgumentValidationError as error:
            return ValidationFailure(error.code, str(error), index)
        if schema.requires_confirmation and not plan.user_confirmed:
            return ValidationFailure(
                ERROR_CONFIRMATION_REQUIRED,
                'user confirmation is required for ' + schema.name,
                index)
    return None
