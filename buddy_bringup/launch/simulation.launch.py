"""Compose the complete Gazebo-first Buddy runtime from bounded launch fragments."""

from __future__ import annotations

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _include(
    package: str,
    launch_file: str,
    arguments: dict[str, object],
    *,
    condition=None,
):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [FindPackageShare(package), "/launch/", launch_file]
        ),
        launch_arguments=arguments.items(),
        condition=condition,
    )


def generate_launch_description() -> LaunchDescription:
    """Launch simulation, autonomy, local dialogue, and safety as separate nodes."""
    use_sim_time = LaunchConfiguration("use_sim_time")
    localization_mode = LaunchConfiguration("localization_mode")
    map_path = LaunchConfiguration("map")
    mapping = IfCondition(
        PythonExpression(["'", localization_mode, "' == 'mapping'"])
    )
    saved = IfCondition(
        PythonExpression(["'", localization_mode, "' == 'saved'"])
    )

    odometry = _include(
        "buddy_localization",
        "odometry_fusion.launch.py",
        {"use_sim_time": use_sim_time},
        condition=mapping,
    )
    slam = _include(
        "buddy_mapping",
        "mapping.launch.py",
        {"use_sim_time": use_sim_time},
        condition=mapping,
    )
    saved_localization = _include(
        "buddy_localization",
        "saved_map_localization.launch.py",
        {"use_sim_time": use_sim_time, "map": map_path},
        condition=saved,
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument(
                "localization_mode",
                default_value="mapping",
                choices=["mapping", "saved"],
            ),
            DeclareLaunchArgument(
                "map",
                default_value="",
                description="Saved map YAML path when localization_mode:=saved.",
            ),
            _include(
                "buddy_gazebo",
                "buddy_sim.launch.py",
                {"use_sim_time": use_sim_time},
            ),
            _include("buddy_safety", "safety_motion.launch.py", {}),
            odometry,
            slam,
            saved_localization,
            _include(
                "buddy_navigation",
                "navigation.launch.py",
                {"use_sim_time": use_sim_time},
            ),
            _include(
                "buddy_perception",
                "perception.launch.py",
                {"use_sim_time": use_sim_time},
            ),
            _include(
                "buddy_world_model",
                "world_model.launch.py",
                {"use_sim_time": use_sim_time},
            ),
            Node(
                package="buddy_bringup",
                executable="status_supervisor",
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
            ),
            Node(
                package="buddy_capabilities",
                executable="capability_registry",
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
            ),
            Node(
                package="buddy_task_executor",
                executable="task_executive",
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
            ),
            Node(
                package="buddy_brain",
                executable="dialogue_node",
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
            ),
            Node(
                package="buddy_voice",
                executable="voice_input",
                name="voice_input",
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
            ),
            Node(
                package="buddy_voice",
                executable="speak_server",
                name="speak_server",
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
            ),
        ]
    )
