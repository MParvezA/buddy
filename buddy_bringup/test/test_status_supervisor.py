"""Component-level liveness tests for the root-owned status supervisor."""

from unittest.mock import patch

from buddy_bringup.status_supervisor import StatusSupervisor
from buddy_interfaces.msg import RobotStatus, SafetyState, WorldSummary
from diagnostic_msgs.msg import DiagnosticStatus
import rclpy
from rclpy.clock import ClockType


class _Recorder:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


def _healthy_inputs():
    safety = SafetyState()
    safety.state = SafetyState.STATE_NORMAL
    safety.motion_permitted = True
    world = WorldSummary()
    world.robot_pose_valid = True
    world.current_location = 'home'
    return safety, world


def test_dependency_liveness_expires_on_steady_time_when_ros_time_can_pause(
    monkeypatch, tmp_path
):
    """A dead dependency cannot leave operator readiness latched healthy."""
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    now = [10.0]
    with patch(
        'buddy_bringup.status_supervisor.time.monotonic',
        side_effect=lambda: now[0],
    ):
        rclpy.init()
        node = StatusSupervisor()
        status_recorder = _Recorder()
        diagnostics_recorder = _Recorder()
        node._status_publisher = status_recorder
        node._diagnostics = diagnostics_recorder
        try:
            safety, world = _healthy_inputs()
            node._on_safety(safety)
            node._on_world(world)
            node._publish()

            assert node._steady_clock.clock_type == ClockType.STEADY_TIME
            assert status_recorder.messages[-1].motion_ready
            assert (
                diagnostics_recorder.messages[-1].status[0].level
                == DiagnosticStatus.OK
            )

            # Keep the world publisher live while the safety publisher dies.
            # ROS time need not advance: both age and the timer use steady time.
            now[0] += 2.0
            node._on_world(world)
            now[0] += 1.0
            node._publish()

            status = status_recorder.messages[-1]
            diagnostic = diagnostics_recorder.messages[-1].status[0]
            values = {item.key: item.value for item in diagnostic.values}
            assert status.motion_ready is False
            assert status.mode == RobotStatus.MODE_BOOTING
            assert diagnostic.level == DiagnosticStatus.ERROR
            assert 'stale' in diagnostic.message
            assert values['safety_received'] == 'true'
            assert values['world_received'] == 'true'
            assert values['safety_fresh'] == 'false'
            assert values['world_fresh'] == 'true'
        finally:
            node.destroy_node()
            rclpy.shutdown()


def test_unreceived_dependencies_are_warning_not_stale_fault(
    monkeypatch, tmp_path
):
    """Startup remains distinguishable from loss of a once-live dependency."""
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    node = StatusSupervisor()
    diagnostics_recorder = _Recorder()
    node._diagnostics = diagnostics_recorder
    try:
        node._publish()
        diagnostic = diagnostics_recorder.messages[-1].status[0]
        assert diagnostic.level == DiagnosticStatus.WARN
        assert diagnostic.message == 'waiting for status inputs'
    finally:
        node.destroy_node()
        rclpy.shutdown()
