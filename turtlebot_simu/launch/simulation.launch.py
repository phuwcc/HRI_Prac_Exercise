"""Launch the TurtleBot 4 simulator and its standard RViz view."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    simulator_share = get_package_share_directory('turtlebot4_ignition_bringup')
    simulator_launch = PathJoinSubstitution(
        [simulator_share, 'launch', 'turtlebot4_ignition.launch.py'],
    )

    arguments = [
        DeclareLaunchArgument('model', default_value='standard', choices=['standard', 'lite']),
        DeclareLaunchArgument('world', default_value='maze'),
        DeclareLaunchArgument('rviz', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('namespace', default_value=''),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.0'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        DeclareLaunchArgument(
            'check_topics', default_value='false', choices=['true', 'false'],
            description='Run the one-shot /scan, /odom and /cmd_vel health check.',
        ),
    ]

    simulator = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(simulator_launch),
        launch_arguments={
            'model': LaunchConfiguration('model'),
            'world': LaunchConfiguration('world'),
            'rviz': LaunchConfiguration('rviz'),
            # Stop the complete ROS launch when the Gazebo window is closed.
            'on_exit_shutdown': 'true',
            'namespace': LaunchConfiguration('namespace'),
            'x': LaunchConfiguration('x'),
            'y': LaunchConfiguration('y'),
            'z': LaunchConfiguration('z'),
            'yaw': LaunchConfiguration('yaw'),
        }.items(),
    )

    delayed_check = TimerAction(
        period=20.0,
        actions=[
            Node(
                package='turtlebot_simu',
                executable='topic_check',
                namespace=LaunchConfiguration('namespace'),
                name='topic_check',
                output='screen',
                arguments=['--timeout', '90'],
                condition=IfCondition(LaunchConfiguration('check_topics')),
            ),
        ],
    )

    # This assignment runs entirely on one computer. Limiting DDS discovery to
    # localhost avoids discovery floods from other ROS 2 machines on the LAN.
    local_dds = SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1')

    return LaunchDescription(arguments + [local_dds, simulator, delayed_check])
