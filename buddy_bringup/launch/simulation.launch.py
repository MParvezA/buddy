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
    voice_input_mode = LaunchConfiguration("voice_input_mode")
    speech_provider = LaunchConfiguration("speech_provider")
    model_provider = LaunchConfiguration("model_provider")
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
            DeclareLaunchArgument(
                "voice_input_mode",
                default_value="fake",
                choices=["fake", "external"],
                description=(
                    "Use the deterministic input fixture or accept utterances "
                    "from a separately run terminal push-to-talk process."
                ),
            ),
            DeclareLaunchArgument(
                "speech_provider",
                default_value="fake",
                choices=["fake", "piper"],
            ),
            DeclareLaunchArgument(
                "model_provider",
                default_value="fake",
                choices=["fake", "llama_cpp"],
            ),
            DeclareLaunchArgument("llama_cpp_binary", default_value=""),
            DeclareLaunchArgument("llama_cpp_model", default_value=""),
            DeclareLaunchArgument("llama_cpp_threads", default_value="3"),
            DeclareLaunchArgument("llama_cpp_context_tokens", default_value="4096"),
            DeclareLaunchArgument("llama_cpp_output_tokens", default_value="256"),
            DeclareLaunchArgument("llama_cpp_timeout_seconds", default_value="20.0"),
            DeclareLaunchArgument("llama_cpp_temperature", default_value="0.1"),
            DeclareLaunchArgument("piper_binary", default_value=""),
            DeclareLaunchArgument("piper_playback_binary", default_value="pw-play"),
            DeclareLaunchArgument("piper_en_model", default_value=""),
            DeclareLaunchArgument("piper_en_config", default_value=""),
            DeclareLaunchArgument("piper_de_model", default_value=""),
            DeclareLaunchArgument("piper_de_config", default_value=""),
            DeclareLaunchArgument("piper_en_voice", default_value="en_default"),
            DeclareLaunchArgument("piper_de_voice", default_value="de_default"),
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
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                        "model_provider": model_provider,
                        "llama_cpp_binary": LaunchConfiguration("llama_cpp_binary"),
                        "llama_cpp_model": LaunchConfiguration("llama_cpp_model"),
                        "llama_cpp_threads": LaunchConfiguration("llama_cpp_threads"),
                        "llama_cpp_context_tokens": LaunchConfiguration(
                            "llama_cpp_context_tokens"
                        ),
                        "llama_cpp_output_tokens": LaunchConfiguration(
                            "llama_cpp_output_tokens"
                        ),
                        "llama_cpp_timeout_seconds": LaunchConfiguration(
                            "llama_cpp_timeout_seconds"
                        ),
                        "llama_cpp_temperature": LaunchConfiguration(
                            "llama_cpp_temperature"
                        ),
                        "english_voice": LaunchConfiguration("piper_en_voice"),
                        "german_voice": LaunchConfiguration("piper_de_voice"),
                    }
                ],
                output="screen",
            ),
            Node(
                package="buddy_voice",
                executable="voice_input",
                name="voice_input",
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
                condition=IfCondition(
                    PythonExpression(["'", voice_input_mode, "' == 'fake'"])
                ),
            ),
            Node(
                package="buddy_voice",
                executable="speak_server",
                name="speak_server",
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
                condition=IfCondition(
                    PythonExpression(["'", speech_provider, "' == 'fake'"])
                ),
            ),
            Node(
                package="buddy_voice",
                executable="local_speak_server",
                name="local_speak_server",
                arguments=[
                    "--piper-binary",
                    LaunchConfiguration("piper_binary"),
                    "--playback-binary",
                    LaunchConfiguration("piper_playback_binary"),
                    "--en-model",
                    LaunchConfiguration("piper_en_model"),
                    "--en-config",
                    LaunchConfiguration("piper_en_config"),
                    "--en-voice",
                    LaunchConfiguration("piper_en_voice"),
                    "--de-model",
                    LaunchConfiguration("piper_de_model"),
                    "--de-config",
                    LaunchConfiguration("piper_de_config"),
                    "--de-voice",
                    LaunchConfiguration("piper_de_voice"),
                ],
                parameters=[{"use_sim_time": use_sim_time}],
                output="screen",
                condition=IfCondition(
                    PythonExpression(["'", speech_provider, "' == 'piper'"])
                ),
            ),
        ]
    )
