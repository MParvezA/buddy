"""Launch the minimal raw-sensor readiness boundary."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('buddy_perception'), 'config', 'perception.yaml'
    )
    use_sim_time = LaunchConfiguration('use_sim_time')
    return LaunchDescription(
        [
            DeclareLaunchArgument('use_sim_time', default_value='false'),
            Node(
                package='buddy_perception',
                executable='sensor_readiness',
                namespace='buddy',
                parameters=[config, {'use_sim_time': use_sim_time}],
            ),
        ]
    )
