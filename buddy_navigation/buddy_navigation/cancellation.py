"""Bounded downstream cancellation confirmation."""

import asyncio
from dataclasses import dataclass
import time
from typing import Any


@dataclass(frozen=True)
class StopConfirmation:
    """Evidence that the delegated Nav2 action stopped."""

    confirmed: bool
    message: str


async def confirm_downstream_cancel(
    nav_goal_handle: Any,
    result_future: Any,
    *,
    canceled_status: int,
    timeout_sec: float,
) -> StopConfirmation:
    """Cancel Nav2 and wait for both acknowledgement and canceled terminal state."""
    deadline = time.monotonic() + timeout_sec
    cancel_future = nav_goal_handle.cancel_goal_async()
    while not cancel_future.done():
        if time.monotonic() >= deadline:
            return StopConfirmation(False, 'Nav2 cancellation acknowledgement timed out')
        await asyncio.sleep(0.01)
    cancel_response = cancel_future.result()
    if not cancel_response.goals_canceling:
        return StopConfirmation(False, 'Nav2 did not acknowledge goal cancellation')

    while not result_future.done():
        if time.monotonic() >= deadline:
            return StopConfirmation(False, 'Nav2 canceled terminal state timed out')
        await asyncio.sleep(0.01)
    wrapped_result = result_future.result()
    if wrapped_result.status != canceled_status:
        return StopConfirmation(
            False,
            f'Nav2 stopped with unexpected action status {wrapped_result.status}',
        )
    return StopConfirmation(True, 'Nav2 cancellation and stopped state confirmed')
