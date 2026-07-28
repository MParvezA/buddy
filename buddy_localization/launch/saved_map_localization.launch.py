"""Launch saved-map localization; do not run concurrently with SLAM Toolbox."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory('buddy_localization')
    use_sim_time = LaunchConfiguration('use_sim_time')
    map_yaml = LaunchConfiguration('map')
    params = os.path.join(share, 'config', 'amcl.yaml')
    ekf = os.path.join(share, 'config', 'ekf.yaml')
    return LaunchDescription(
        [
            DeclareLaunchArgument('use_sim_time', default_value='false'),
            DeclareLaunchArgument(
                'map',
                description='Absolute path to a saved occupancy-grid map YAML file.',
            ),
            Node(
                package='robot_localization',
                executable='ekf_node',
                name='ekf_filter_node',
                parameters=[ekf, {'use_sim_time': use_sim_time}],
                remappings=[('odometry/filtered', '/odometry/filtered')],
            ),
            Node(
                package='nav2_map_server',
                executable='map_server',
                name='map_server',
                parameters=[
                    params,
                    {'use_sim_time': use_sim_time, 'yaml_filename': map_yaml},
                ],
            ),
            Node(
                package='nav2_amcl',
                executable='amcl',
                name='amcl',
                parameters=[params, {'use_sim_time': use_sim_time}],
            ),
            Node(
                package='nav2_lifecycle_manager',
                executable='lifecycle_manager',
                name='lifecycle_manager_localization',
                parameters=[
                    params,
                    {
                        'use_sim_time': use_sim_time,
                        'autostart': True,
                        'node_names': ['map_server', 'amcl'],
                    },
                ],
            ),
        ]
    )
