"""Bounded executor teardown that reports failures without skipping cleanup."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutorTeardownReport:
    """Outcomes collected while draining callbacks and joining workers."""

    cancelled_sources: tuple[str, ...]
    errors: tuple[str, ...]


def drain_and_stop_workers(
    executor: Any,
    *,
    drain_timeout_sec: float,
    worker_timeout_sec: float,
) -> ExecutorTeardownReport:
    """Attempt both teardown phases even when callback draining fails."""
    cancelled_sources = ()
    errors = []
    try:
        cancelled_sources = executor.drain_submitted_callbacks(
            drain_timeout_sec
        )
    except Exception as error:
        errors.append(
            f'executor callback drain failed: {type(error).__name__}: {error}'
        )
    try:
        executor.shutdown_workers(worker_timeout_sec)
    except Exception as error:
        errors.append(
            f'executor worker shutdown failed: {type(error).__name__}: {error}'
        )
    return ExecutorTeardownReport(cancelled_sources, tuple(errors))
