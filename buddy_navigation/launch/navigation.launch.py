"""Launch the bounded Nav2 stack and Buddy named-location adapter."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


NAVIGATION_REQUEST_TOPIC = '/buddy/motion/request/navigation'
PRIVATE_NAV2_VELOCITY_TOPIC = '/buddy/navigation/cmd_vel_smoothed'


def generate_launch_description():
    params = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    default_params = os.path.join(
        get_package_share_directory('buddy_navigation'), 'config', 'nav2.yaml'
    )
    common = {'use_sim_time': use_sim_time}
    tf_remaps = [('/tf', '/tf'), ('/tf_static', '/tf_static')]

    nodes = [
        Node(
            package='nav2_controller',
            executable='controller_server',
            name='controller_server',
            parameters=[params, common],
            remappings=tf_remaps + [('cmd_vel', 'cmd_vel_nav')],
        ),
        Node(
            package='nav2_planner',
            executable='planner_server',
            name='planner_server',
            parameters=[params, common],
            remappings=tf_remaps,
        ),
        Node(
            package='nav2_smoother',
            executable='smoother_server',
            name='smoother_server',
            parameters=[params, common],
            remappings=tf_remaps,
        ),
        Node(
            package='nav2_behaviors',
            executable='behavior_server',
            name='behavior_server',
            parameters=[params, common],
            remappings=tf_remaps + [('cmd_vel', 'cmd_vel_nav')],
        ),
        Node(
            package='nav2_velocity_smoother',
            executable='velocity_smoother',
            name='velocity_smoother',
            parameters=[params, common],
            remappings=[
                ('cmd_vel', 'cmd_vel_nav'),
                ('cmd_vel_smoothed', PRIVATE_NAV2_VELOCITY_TOPIC),
            ],
        ),
        Node(
            package='nav2_bt_navigator',
            executable='bt_navigator',
            name='bt_navigator',
            parameters=[params, common],
            remappings=tf_remaps,
        ),
        Node(
            package='nav2_waypoint_follower',
            executable='waypoint_follower',
            name='waypoint_follower',
            parameters=[params, common],
            remappings=tf_remaps,
        ),
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_navigation',
            parameters=[
                params,
                common,
                {
                    'autostart': True,
                    'node_names': [
                        'controller_server',
                        'planner_server',
                        'smoother_server',
                        'behavior_server',
                        'velocity_smoother',
                        'bt_navigator',
                        'waypoint_follower',
                    ],
                },
            ],
        ),
        Node(
            package='buddy_navigation',
            executable='named_navigation_adapter',
            namespace='buddy',
            parameters=[params, common],
        ),
        Node(
            package='buddy_navigation',
            executable='velocity_boundary',
            namespace='buddy',
            parameters=[params, common],
        ),
    ]
    return LaunchDescription(
        [
            DeclareLaunchArgument('use_sim_time', default_value='false'),
            DeclareLaunchArgument('params_file', default_value=default_params),
            *nodes,
        ]
    )
