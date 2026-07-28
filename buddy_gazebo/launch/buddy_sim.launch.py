"""Launch Buddy's deterministic, native Gazebo Harmonic smoke environment."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackagePrefix, FindPackageShare


def generate_launch_description():
    gazebo_share = FindPackageShare('buddy_gazebo')
    description_share = FindPackageShare('buddy_description')
    use_sim_time = LaunchConfiguration('use_sim_time')
    world = PathJoinSubstitution([gazebo_share, 'worlds', 'buddy_smoke.sdf'])
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', PathJoinSubstitution([gazebo_share, 'models'])),
        SetEnvironmentVariable(
            'GZ_SIM_SYSTEM_PLUGIN_PATH',
            [PathJoinSubstitution([FindPackagePrefix('buddy_gazebo'), 'lib']), ':',
             EnvironmentVariable('GZ_SIM_SYSTEM_PLUGIN_PATH', default_value='')]),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(PathJoinSubstitution([
            FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py'])),
            launch_arguments={'gz_args': ['-r -s ', world]}.items()),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'use_sim_time': use_sim_time,
                          'robot_description': Command(['xacro ', PathJoinSubstitution([description_share, 'urdf', 'buddy.urdf.xacro'])])}]),
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='buddy_sensor_bridge',
             parameters=[{'config_file': PathJoinSubstitution([gazebo_share, 'config', 'bridge.yaml']),
                          'use_sim_time': use_sim_time}]),
        Node(package='buddy_gazebo', executable='safe_cmd_vel_adapter',
             parameters=[{'use_sim_time': use_sim_time}]),
    ])
