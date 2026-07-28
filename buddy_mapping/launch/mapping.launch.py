"""Launch mapping mode, which owns map-to-odom instead of AMCL."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('buddy_mapping'),
        'config',
        'slam_toolbox.yaml',
    )
    online_async_launch = os.path.join(
        get_package_share_directory('slam_toolbox'),
        'launch',
        'online_async_launch.py',
    )
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    return LaunchDescription(
        [
            DeclareLaunchArgument('use_sim_time', default_value='false'),
            DeclareLaunchArgument('autostart', default_value='true'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(online_async_launch),
                launch_arguments={
                    'slam_params_file': config,
                    'use_sim_time': use_sim_time,
                    'autostart': autostart,
                    'use_lifecycle_manager': 'false',
                }.items(),
            ),
        ]
    )
