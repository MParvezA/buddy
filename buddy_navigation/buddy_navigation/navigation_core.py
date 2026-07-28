"""ROS-independent navigation outcome and precondition policy."""

from dataclasses import dataclass
from enum import IntEnum


class Outcome(IntEnum):
    """Frozen NavigateToNamedLocation result values."""

    SUCCEEDED = 0
    CANCELLED = 1
    UNKNOWN_LOCATION = 2
    UNREACHABLE = 3
    LOCALIZATION_UNAVAILABLE = 4
    SAFETY_STOP = 5
    FAILED = 6


@dataclass(frozen=True)
class Decision:
    """Structured decision returned by the adapter core."""

    outcome: Outcome
    message: str


def check_preconditions(
    *,
    location_found: bool,
    localization_available: bool,
    safety_state_received: bool,
    motion_permitted: bool,
) -> Decision | None:
    """Return a failure decision, preserving deterministic check ordering."""
    if not location_found:
        return Decision(Outcome.UNKNOWN_LOCATION, 'named location was not found')
    if not localization_available:
        return Decision(
            Outcome.LOCALIZATION_UNAVAILABLE,
            'map to base_link localization transform is unavailable',
        )
    if not safety_state_received:
        return Decision(Outcome.SAFETY_STOP, 'authoritative safety state is unavailable')
    if not motion_permitted:
        return Decision(Outcome.SAFETY_STOP, 'safety state inhibits motion')
    return None


def nav2_terminal_outcome(status: int, *, succeeded_status: int, canceled_status: int) -> Decision:
    """Map a standard ROS action terminal status into the frozen outcome set."""
    if status == succeeded_status:
        return Decision(Outcome.SUCCEEDED, 'navigation succeeded')
    if status == canceled_status:
        return Decision(Outcome.CANCELLED, 'navigation was cancelled')
    return Decision(Outcome.UNREACHABLE, 'Nav2 could not reach the named location')
