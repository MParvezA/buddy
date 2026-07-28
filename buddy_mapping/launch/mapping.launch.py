"""Launch mapping mode, which owns map-to-odom instead of AMCL."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('buddy_mapping'),
        'config',
        'slam_toolbox.yaml',
    )
    use_sim_time = LaunchConfiguration('use_sim_time')
    return LaunchDescription(
        [
            DeclareLaunchArgument('use_sim_time', default_value='false'),
            Node(
                package='slam_toolbox',
                executable='async_slam_toolbox_node',
                name='slam_toolbox',
                parameters=[config, {'use_sim_time': use_sim_time}],
            ),
        ]
    )
