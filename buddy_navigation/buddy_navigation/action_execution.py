"""Action execution boundary that prevents successful default failure payloads."""

from typing import Any, Callable


def execute_with_failure_result(
    adapter: Any,
    goal_handle: Any,
    execute_goal: Callable[[Any], Any],
):
    """Convert an unexpected action callback exception into a structured result."""
    try:
        return execute_goal(goal_handle)
    except Exception as error:
        return adapter._finish_unexpected_failure(goal_handle, error)
