from pathlib import Path

import yaml


PACKAGE = Path(__file__).parents[1]


def test_nav2_velocity_has_one_external_output_boundary():
    launch_text = (PACKAGE / 'launch' / 'navigation.launch.py').read_text()
    assert launch_text.count(
        "('cmd_vel_smoothed', PRIVATE_NAV2_VELOCITY_TOPIC)"
    ) == 1
    assert "NAVIGATION_REQUEST_TOPIC = '/buddy/motion/request/navigation'" in launch_text
    assert launch_text.count("executable='velocity_boundary'") == 1
    assert '/buddy/motion/safe_cmd_vel' not in launch_text
    assert '/buddy/motion/arbitrated_cmd_vel' not in launch_text
    assert 'buddy_base_controller' not in launch_text


def test_nav2_frames_topics_and_sim_time_are_contract_values():
    params = yaml.safe_load((PACKAGE / 'config' / 'nav2.yaml').read_text())
    assert params['bt_navigator']['ros__parameters']['global_frame'] == 'map'
    assert params['bt_navigator']['ros__parameters']['robot_base_frame'] == 'base_link'
    assert params['bt_navigator']['ros__parameters']['odom_topic'] == '/odometry/filtered'
    for name, section in params.items():
        node_parameters = (
            section[name]['ros__parameters']
            if name in ('local_costmap', 'global_costmap')
            else section['ros__parameters']
        )
        assert 'use_sim_time' in node_parameters
    assert params['controller_server']['ros__parameters']['enable_stamped_cmd_vel']
    assert params['behavior_server']['ros__parameters']['enable_stamped_cmd_vel']
    assert params['velocity_smoother']['ros__parameters']['enable_stamped_cmd_vel']
    local_costmap = params['local_costmap']['local_costmap']['ros__parameters']
    global_costmap = params['global_costmap']['global_costmap']['ros__parameters']
    assert local_costmap['global_frame'] == 'odom'
    assert global_costmap['global_frame'] == 'map'


def test_costmaps_allow_bounded_time_for_startup_tf():
    params = yaml.safe_load((PACKAGE / 'config' / 'nav2.yaml').read_text())
    local_costmap = params['local_costmap']['local_costmap']['ros__parameters']
    global_costmap = params['global_costmap']['global_costmap']['ros__parameters']
    assert local_costmap['initial_transform_timeout'] == 20.0
    assert global_costmap['initial_transform_timeout'] == 20.0


def test_action_owner_lease_has_periodic_status_margin():
    params = yaml.safe_load((PACKAGE / 'config' / 'nav2.yaml').read_text())
    heartbeat_period = params[
        'named_navigation_adapter'
    ]['ros__parameters']['owner_status_heartbeat_period_sec']
    liveness_timeout = params[
        'navigation_velocity_boundary'
    ]['ros__parameters']['owner_liveness_timeout_sec']

    assert heartbeat_period == 0.05
    assert liveness_timeout == 0.2
    assert heartbeat_period > 0.0
    assert liveness_timeout >= 3.0 * heartbeat_period
    assert liveness_timeout + 0.05 <= 0.25


def test_slam_global_costmap_is_a_robot_centered_bounded_window():
    params = yaml.safe_load((PACKAGE / 'config' / 'nav2.yaml').read_text())
    global_costmap = params['global_costmap']['global_costmap']['ros__parameters']

    assert global_costmap['rolling_window'] is True
    assert global_costmap['width'] == 20
    assert global_costmap['height'] == 20
