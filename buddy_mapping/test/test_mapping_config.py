from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


PACKAGE = Path(__file__).parents[1]


def test_slam_owns_map_to_odom_in_mapping_mode():
    params = yaml.safe_load(
        (PACKAGE / 'config' / 'slam_toolbox.yaml').read_text()
    )['slam_toolbox']['ros__parameters']
    assert params['mode'] == 'mapping'
    assert params['map_frame'] == 'map'
    assert params['odom_frame'] == 'odom'
    assert params['base_frame'] == 'base_link'
    assert params['scan_topic'] == '/scan'
    assert params['transform_publish_period'] > 0.0
    assert params['use_sim_time'] is False


def test_mapping_launch_does_not_start_competing_localization():
    launch = (PACKAGE / 'launch' / 'mapping.launch.py').read_text()
    assert 'amcl' not in launch
    assert 'robot_localization' not in launch


def test_mapping_launch_delegates_slam_lifecycle_autostart():
    launch = (PACKAGE / 'launch' / 'mapping.launch.py').read_text()
    assert 'IncludeLaunchDescription' in launch
    assert 'online_async_launch.py' in launch
    assert "'slam_params_file': config" in launch
    assert "'autostart': autostart" in launch


def test_slam_laser_range_matches_production_lidar():
    params = yaml.safe_load(
        (PACKAGE / 'config' / 'slam_toolbox.yaml').read_text()
    )['slam_toolbox']['ros__parameters']
    model_path = (
        Path(__file__).resolve().parents[2]
        / 'buddy_gazebo'
        / 'models'
        / 'buddy'
        / 'model.sdf'
    )
    model = ET.parse(model_path)
    lidar_max = float(
        model.findtext(".//sensor[@type='gpu_lidar']/lidar/range/max")
    )

    assert float(params['max_laser_range']) == lidar_max
