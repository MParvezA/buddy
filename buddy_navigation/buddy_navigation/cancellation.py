"""Bounded downstream cancellation confirmation."""

from dataclasses import dataclass
import time
from typing import Any


@dataclass(frozen=True)
class StopConfirmation:
    """Evidence that the delegated Nav2 action stopped."""

    confirmed: bool
    message: str


def _wait_for_completion(
    future: Any,
    *,
    deadline: float,
    timeout_message: str,
    failure_message: str,
) -> StopConfirmation | None:
    while True:
        try:
            if future.done():
                return None
        except Exception as error:
            return StopConfirmation(False, f'{failure_message}: {error}')
        if time.monotonic() >= deadline:
            return StopConfirmation(False, timeout_message)
        time.sleep(0.01)


def confirm_downstream_cancel(
    nav_goal_handle: Any,
    result_future: Any,
    *,
    canceled_status: int,
    timeout_sec: float,
) -> StopConfirmation:
    """Cancel Nav2 and wait for both acknowledgement and canceled terminal state."""
    deadline = time.monotonic() + timeout_sec
    try:
        cancel_future = nav_goal_handle.cancel_goal_async()
    except Exception as error:
        return StopConfirmation(
            False,
            f'Nav2 cancellation request failed: {error}',
        )
    if cancel_future is None:
        return StopConfirmation(False, 'Nav2 cancellation future is unavailable')
    wait_failure = _wait_for_completion(
        cancel_future,
        deadline=deadline,
        timeout_message='Nav2 cancellation acknowledgement timed out',
        failure_message='Nav2 cancellation acknowledgement failed',
    )
    if wait_failure is not None:
        return wait_failure
    try:
        cancel_error = cancel_future.exception()
    except Exception as error:
        return StopConfirmation(
            False,
            f'Nav2 cancellation acknowledgement failed: {error}',
        )
    if cancel_error is not None:
        return StopConfirmation(
            False,
            f'Nav2 cancellation acknowledgement failed: {cancel_error}',
        )
    try:
        cancel_response = cancel_future.result()
    except Exception as error:
        return StopConfirmation(
            False,
            f'Nav2 cancellation acknowledgement failed: {error}',
        )
    if not getattr(cancel_response, 'goals_canceling', None):
        return StopConfirmation(False, 'Nav2 did not acknowledge goal cancellation')

    if result_future is None:
        return StopConfirmation(False, 'Nav2 result future is unavailable')
    wait_failure = _wait_for_completion(
        result_future,
        deadline=deadline,
        timeout_message='Nav2 canceled terminal state timed out',
        failure_message='Nav2 canceled terminal result failed',
    )
    if wait_failure is not None:
        return wait_failure
    try:
        result_error = result_future.exception()
    except Exception as error:
        return StopConfirmation(
            False,
            f'Nav2 canceled terminal result failed: {error}',
        )
    if result_error is not None:
        return StopConfirmation(
            False,
            f'Nav2 canceled terminal result failed: {result_error}',
        )
    try:
        wrapped_result = result_future.result()
    except Exception as error:
        return StopConfirmation(
            False,
            f'Nav2 canceled terminal result failed: {error}',
        )
    status = getattr(wrapped_result, 'status', None)
    if status != canceled_status:
        return StopConfirmation(
            False,
            f'Nav2 stopped with unexpected action status {status}',
        )
    return StopConfirmation(True, 'Nav2 cancellation and stopped state confirmed')
