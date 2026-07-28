"""Pure status aggregation policy for the Buddy supervisor."""

from __future__ import annotations

from dataclasses import dataclass

from buddy_interfaces.msg import RobotStatus, SafetyState, WorldSummary


@dataclass(frozen=True)
class StatusDecision:
    """Fields published by the authoritative low-rate status adapter."""

    mode: int
    localization_state: int
    motion_ready: bool
    current_location: str


def decide_status(
    safety: SafetyState | None,
    world: WorldSummary | None,
) -> StatusDecision:
    """Combine independently latched safety and summarized world state."""
    if safety is None:
        mode = RobotStatus.MODE_BOOTING
    elif (
        safety.state == SafetyState.STATE_EMERGENCY_STOPPED
        or safety.emergency_stop_latched
    ):
        mode = RobotStatus.MODE_EMERGENCY_STOP
    elif safety.state == SafetyState.STATE_FAULT:
        mode = RobotStatus.MODE_FAULT
    elif safety.state in (
        SafetyState.STATE_SOFT_STOPPED,
        SafetyState.STATE_LIMITED,
    ):
        mode = RobotStatus.MODE_DEGRADED
    else:
        mode = RobotStatus.MODE_IDLE

    if world is None:
        localization = RobotStatus.LOCALIZATION_UNKNOWN
        location = ''
    elif world.robot_pose_valid:
        localization = RobotStatus.LOCALIZATION_GOOD
        location = world.current_location
    else:
        localization = RobotStatus.LOCALIZATION_UNAVAILABLE
        location = ''

    motion_ready = bool(
        safety is not None
        and safety.motion_permitted
        and not safety.emergency_stop_latched
        and safety.state in (
            SafetyState.STATE_NORMAL,
            SafetyState.STATE_LIMITED,
        )
        and localization == RobotStatus.LOCALIZATION_GOOD
    )
    return StatusDecision(mode, localization, motion_ready, location)
