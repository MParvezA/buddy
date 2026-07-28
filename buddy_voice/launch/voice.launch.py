"""Bounded local voice launch fragment; global composition remains root-owned."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """Start local push-to-talk recognition and mock-backed speech output."""
    return LaunchDescription([
        Node(package='buddy_voice', executable='voice_input', name='voice_input'),
        Node(package='buddy_voice', executable='speak_server', name='speak_server'),
    ])
