from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory('buddy_safety')) / 'config' / 'safety.yaml'
    return LaunchDescription(
        [
            Node(
                package='buddy_safety',
                executable='command_arbiter',
                output='screen',
                parameters=[str(config)],
            ),
            Node(
                package='buddy_safety',
                executable='safety_filter',
                output='screen',
                parameters=[str(config)],
            ),
        ]
    )
