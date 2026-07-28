import time

from action_msgs.msg import GoalStatus, GoalStatusArray
from buddy_navigation.velocity_boundary import (
    ACTION_STATUS_TOPIC,
    DIAGNOSTIC_NAME,
    DIAGNOSTICS_TOPIC,
    motion_request_qos,
    NAVIGATION_REQUEST_TOPIC,
    PRIVATE_NAV2_TOPIC,
    VelocityBoundary,
)
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from geometry_msgs.msg import TwistStamped
import pytest
import rclpy
from rclpy.clock import ClockType
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import Parameter
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)


COMMAND_FRESHNESS_BOUND_SEC = 0.25
CI_SCHEDULING_TOLERANCE_SEC = 0.05


def _values(status):
    return {value.key: value.value for value in status.values}


def _spin_until(executor, predicate, timeout_sec=1.0):
    deadline = time.monotonic() + timeout_sec
    while not predicate() and time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.01)
    assert predicate()


def test_motion_request_qos_is_exactly_frozen_profile():
    qos = motion_request_qos()
    assert qos.history == HistoryPolicy.KEEP_LAST
    assert qos.depth == 1
    assert qos.reliability == ReliabilityPolicy.RELIABLE
    assert qos.durability == DurabilityPolicy.VOLATILE


def test_runtime_graph_exposes_stamped_navigation_request(monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    node = VelocityBoundary()
    observer = rclpy.create_node('velocity_boundary_graph_test')
    try:
        rclpy.spin_once(observer, timeout_sec=0.1)
        endpoints = observer.get_publishers_info_by_topic(NAVIGATION_REQUEST_TOPIC)
        ours = [endpoint for endpoint in endpoints if endpoint.node_name == node.get_name()]
        assert len(ours) == 1
        endpoint = ours[0]
        assert endpoint.topic_type == 'geometry_msgs/msg/TwistStamped'
        runtime_qos = node._publisher.qos_profile
        assert runtime_qos.history == HistoryPolicy.KEEP_LAST
        assert runtime_qos.depth == 1
        assert runtime_qos.reliability == ReliabilityPolicy.RELIABLE
        assert runtime_qos.durability == DurabilityPolicy.VOLATILE
    finally:
        observer.destroy_node()
        node.destroy_node()
        rclpy.shutdown()


def test_startup_publishes_single_structured_gate_inactive_diagnostic(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    observer = rclpy.create_node('velocity_startup_diagnostic_observer')
    diagnostics = []
    observer.create_subscription(
        DiagnosticArray,
        DIAGNOSTICS_TOPIC,
        diagnostics.append,
        10,
    )
    node = VelocityBoundary()
    executor = SingleThreadedExecutor()
    executor.add_node(observer)
    executor.add_node(node)
    try:
        _spin_until(executor, lambda: bool(diagnostics))
        for _ in range(10):
            executor.spin_once(timeout_sec=0.01)

        statuses = [
            status
            for message in diagnostics
            for status in message.status
            if status.name == DIAGNOSTIC_NAME
        ]
        assert len(statuses) == 1
        status = statuses[0]
        values = _values(status)
        assert status.level == DiagnosticStatus.WARN
        assert values['state'] == 'gate_inactive'
        assert values['gate_active'] == 'false'
        assert values['reason'] == 'startup_awaiting_action'
        assert values['owner_elapsed_sec'] == 'not_available'
        assert values['owner_lease_sec'] == '0.200000'
        assert values['liveness_clock'] == 'steady_time'
    finally:
        executor.shutdown()
        observer.destroy_node()
        node.destroy_node()
        rclpy.shutdown()


def test_action_cancellation_closes_velocity_gate_and_publishes_zero(
    monkeypatch, tmp_path
):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    node = VelocityBoundary()
    observer = rclpy.create_node('velocity_gate_test')
    received = []
    diagnostics = []
    observer.create_subscription(
        TwistStamped,
        NAVIGATION_REQUEST_TOPIC,
        received.append,
        motion_request_qos(),
    )
    observer.create_subscription(
        DiagnosticArray,
        DIAGNOSTICS_TOPIC,
        diagnostics.append,
        10,
    )
    try:
        discovery_deadline = time.monotonic() + 1.0
        while (
            node._diagnostics.get_subscription_count() == 0
            and time.monotonic() < discovery_deadline
        ):
            rclpy.spin_once(observer, timeout_sec=0.01)
        assert node._diagnostics.get_subscription_count() == 1

        executing = GoalStatusArray()
        executing.status_list = [GoalStatus(status=GoalStatus.STATUS_EXECUTING)]
        node._on_action_status(executing)
        command = TwistStamped()
        command.twist.linear.x = 0.2
        node._forward(command)
        rclpy.spin_once(observer, timeout_sec=0.2)

        canceling = GoalStatusArray()
        canceling.status_list = [GoalStatus(status=GoalStatus.STATUS_CANCELING)]
        node._on_action_status(canceling)
        node._forward(command)
        rclpy.spin_once(observer, timeout_sec=0.2)
        rclpy.spin_once(observer, timeout_sec=0.2)
        diagnostic_deadline = time.monotonic() + 1.0
        while (
            not any(
                _values(status)['reason'] == 'action_no_longer_executing'
                for message in diagnostics
                for status in message.status
                if status.name == DIAGNOSTIC_NAME
            )
            and time.monotonic() < diagnostic_deadline
        ):
            rclpy.spin_once(observer, timeout_sec=0.01)

        assert len(received) == 2
        assert received[0].twist.linear.x == 0.2
        assert received[1].twist.linear.x == 0.0
        assert received[1].twist.angular.z == 0.0
        statuses = [
            status
            for message in diagnostics
            for status in message.status
            if status.name == DIAGNOSTIC_NAME
        ]
        terminal = next(
            status
            for status in statuses
            if _values(status)['reason'] == 'action_no_longer_executing'
        )
        terminal_values = _values(terminal)
        assert terminal.level == DiagnosticStatus.OK
        assert terminal_values['state'] == 'gate_inactive'
        assert terminal_values['gate_active'] == 'false'
        assert terminal_values['owner_elapsed_sec'] != 'not_available'
    finally:
        observer.destroy_node()
        node.destroy_node()
        rclpy.shutdown()


def test_stale_action_owner_closes_gate_with_sim_time_paused(
    monkeypatch, tmp_path
):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    node = VelocityBoundary(
        parameter_overrides=[
            Parameter('use_sim_time', value=True),
        ],
    )
    observer = rclpy.create_node('velocity_owner_liveness_test')
    received = []
    diagnostics = []
    observer.create_subscription(
        TwistStamped,
        NAVIGATION_REQUEST_TOPIC,
        received.append,
        motion_request_qos(),
    )
    observer.create_subscription(
        DiagnosticArray,
        DIAGNOSTICS_TOPIC,
        diagnostics.append,
        10,
    )
    try:
        assert (
            node._owner_liveness_timer.clock.clock_type
            == ClockType.STEADY_TIME
        )
        executing = GoalStatusArray()
        executing.status_list = [
            GoalStatus(status=GoalStatus.STATUS_EXECUTING)
        ]
        node._on_action_status(executing)
        command = TwistStamped()
        command.twist.linear.x = 0.2

        started = time.monotonic()
        deadline = (
            started
            + COMMAND_FRESHNESS_BOUND_SEC
            + CI_SCHEDULING_TOLERANCE_SEC
        )
        while time.monotonic() < deadline:
            node._forward(command)
            rclpy.spin_once(node, timeout_sec=0.005)
            rclpy.spin_once(observer, timeout_sec=0.005)
            if any(message.twist.linear.x == 0.0 for message in received):
                break

        zero_index = next(
            index
            for index, message in enumerate(received)
            if message.twist.linear.x == 0.0
        )
        zero_elapsed = time.monotonic() - started
        for _ in range(5):
            node._forward(command)
            rclpy.spin_once(node, timeout_sec=0.005)
            rclpy.spin_once(observer, timeout_sec=0.005)

        assert node.get_clock().now().nanoseconds == 0
        assert any(
            message.twist.linear.x == 0.2
            for message in received[:zero_index]
        )
        assert zero_elapsed <= (
            COMMAND_FRESHNESS_BOUND_SEC
            + CI_SCHEDULING_TOLERANCE_SEC
        )
        assert sum(
            message.twist.linear.x == 0.0 for message in received
        ) == 1
        assert all(
            message.twist.linear.x == 0.0
            for message in received[zero_index:]
        )
        statuses = [
            status
            for message in diagnostics
            for status in message.status
            if status.name == DIAGNOSTIC_NAME
        ]
        timeout_statuses = [
            status
            for status in statuses
            if _values(status)['reason'] == 'owner_liveness_timeout'
        ]
        assert len(timeout_statuses) == 1
        timeout_status = timeout_statuses[0]
        timeout_values = _values(timeout_status)
        assert timeout_status.level == DiagnosticStatus.ERROR
        assert timeout_values['state'] == 'gate_inactive'
        assert timeout_values['gate_active'] == 'false'
        assert (
            float(timeout_values['owner_elapsed_sec'])
            >= float(timeout_values['owner_lease_sec'])
        )
        assert timeout_values['owner_lease_sec'] == '0.200000'
        assert timeout_values['liveness_clock'] == 'steady_time'

        node._on_action_status(executing)
        rclpy.spin_once(observer, timeout_sec=0.2)
        restored_statuses = [
            status
            for message in diagnostics
            for status in message.status
            if status.name == DIAGNOSTIC_NAME
            and _values(status)['reason'] == 'executing_action_status'
        ]
        assert restored_statuses
        assert restored_statuses[-1].level == DiagnosticStatus.OK
        assert _values(restored_statuses[-1])['gate_active'] == 'true'
    finally:
        observer.destroy_node()
        node.destroy_node()
        rclpy.shutdown()


def test_owner_timeout_zero_and_error_are_one_transition(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    node = VelocityBoundary()
    events = []

    class Recorder:
        def __init__(self, kind):
            self.kind = kind

        def publish(self, message):
            events.append((self.kind, message))

    try:
        node._publisher = Recorder('motion')
        node._diagnostics = Recorder('diagnostic')
        node._action_executing = True
        node._last_owner_evidence_ns = (
            node._owner_liveness_clock.now().nanoseconds
            - int((node._owner_liveness_timeout_sec + 0.01) * 1e9)
        )

        node._check_owner_liveness()

        assert [kind for kind, _ in events] == ['motion', 'diagnostic']
        stopped = events[0][1]
        assert stopped.twist.linear.x == 0.0
        assert stopped.twist.angular.z == 0.0
        status = events[1][1].status[0]
        values = _values(status)
        assert status.level == DiagnosticStatus.ERROR
        assert values['reason'] == 'owner_liveness_timeout'
        assert float(values['owner_elapsed_sec']) >= float(
            values['owner_lease_sec']
        )

        node._check_owner_liveness()
        assert len(events) == 2
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_owner_evidence_publisher_loss_stops_persistent_nav2_commands(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    boundary = VelocityBoundary(
        parameter_overrides=[
            Parameter('use_sim_time', value=True),
        ],
    )
    owner = rclpy.create_node('named_adapter_owner_evidence')
    nav2 = rclpy.create_node('persistent_nav2_velocity_source')
    observer = rclpy.create_node('owner_loss_velocity_observer')
    status_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    nav2_input_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )
    owner_status = owner.create_publisher(
        GoalStatusArray,
        ACTION_STATUS_TOPIC,
        status_qos,
    )
    nav2_commands = nav2.create_publisher(
        TwistStamped,
        PRIVATE_NAV2_TOPIC,
        nav2_input_qos,
    )
    received = []
    observer.create_subscription(
        TwistStamped,
        NAVIGATION_REQUEST_TOPIC,
        received.append,
        motion_request_qos(),
    )
    executor = SingleThreadedExecutor()
    for runtime_node in (boundary, owner, nav2, observer):
        executor.add_node(runtime_node)
    owner_destroyed = False
    try:
        executing = GoalStatusArray()
        executing.status_list = [
            GoalStatus(status=GoalStatus.STATUS_EXECUTING)
        ]
        command = TwistStamped()
        command.twist.linear.x = 0.2
        discovery_deadline = time.monotonic() + 1.0
        while (
            not any(message.twist.linear.x == 0.2 for message in received)
            and time.monotonic() < discovery_deadline
        ):
            owner_status.publish(executing)
            nav2_commands.publish(command)
            executor.spin_once(timeout_sec=0.01)
        assert any(message.twist.linear.x == 0.2 for message in received)

        owner_lost_at = time.monotonic()
        executor.remove_node(owner)
        owner.destroy_node()
        owner_destroyed = True
        zero_index = None
        zero_deadline = (
            owner_lost_at
            + COMMAND_FRESHNESS_BOUND_SEC
            + CI_SCHEDULING_TOLERANCE_SEC
        )
        while time.monotonic() < zero_deadline:
            nav2_commands.publish(command)
            executor.spin_once(timeout_sec=0.005)
            zero_index = next(
                (
                    index
                    for index, message in enumerate(received)
                    if message.twist.linear.x == 0.0
                ),
                None,
            )
            if zero_index is not None:
                break

        assert zero_index is not None
        zero_elapsed = time.monotonic() - owner_lost_at
        for _ in range(5):
            nav2_commands.publish(command)
            executor.spin_once(timeout_sec=0.005)

        assert zero_elapsed <= (
            COMMAND_FRESHNESS_BOUND_SEC
            + CI_SCHEDULING_TOLERANCE_SEC
        )
        assert sum(
            message.twist.linear.x == 0.0 for message in received
        ) == 1
        assert all(
            message.twist.linear.x == 0.0
            for message in received[zero_index:]
        )
    finally:
        executor.shutdown()
        if not owner_destroyed:
            owner.destroy_node()
        for runtime_node in (boundary, nav2, observer):
            runtime_node.destroy_node()
        rclpy.shutdown()


def test_owner_liveness_timeout_rejects_nan(monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init()
    try:
        with pytest.raises(
            ValueError,
            match='owner_liveness_timeout_sec must be finite and positive',
        ):
            VelocityBoundary(
                parameter_overrides=[
                    Parameter(
                        'owner_liveness_timeout_sec',
                        value=float('nan'),
                    ),
                ],
            )
    finally:
        rclpy.shutdown()
