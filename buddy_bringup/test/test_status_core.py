"""Tests for the pure root-owned status aggregation policy."""

from buddy_bringup.status_core import decide_status

from buddy_interfaces.msg import RobotStatus, SafetyState, WorldSummary


def test_missing_inputs_boot_motion_inhibited():
    """Missing safety and world summaries keep startup motion inhibited."""
    decision = decide_status(None, None)
    assert decision.mode == RobotStatus.MODE_BOOTING
    assert decision.localization_state == RobotStatus.LOCALIZATION_UNKNOWN
    assert decision.motion_ready is False


def test_good_world_and_normal_safety_permit_motion():
    """Good localization and normal safety produce a motion-ready status."""
    safety = SafetyState()
    safety.state = SafetyState.STATE_NORMAL
    safety.motion_permitted = True
    world = WorldSummary()
    world.robot_pose_valid = True
    world.current_location = 'home'
    decision = decide_status(safety, world)
    assert decision.mode == RobotStatus.MODE_IDLE
    assert decision.localization_state == RobotStatus.LOCALIZATION_GOOD
    assert decision.motion_ready
    assert decision.current_location == 'home'


def test_emergency_stop_overrides_other_inputs():
    """A latched emergency stop overrides otherwise healthy inputs."""
    safety = SafetyState()
    safety.state = SafetyState.STATE_EMERGENCY_STOPPED
    safety.motion_permitted = True
    safety.emergency_stop_latched = True
    world = WorldSummary()
    world.robot_pose_valid = True
    decision = decide_status(safety, world)
    assert decision.mode == RobotStatus.MODE_EMERGENCY_STOP
    assert decision.motion_ready is False
