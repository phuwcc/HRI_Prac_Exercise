"""Launch TurtleBot 4 simulation, SLAM Toolbox and a mapping RViz view."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from turtlebot_simu.launch_support import world_launch_arguments


def generate_launch_description() -> LaunchDescription:
    simulator_share = get_package_share_directory('turtlebot4_ignition_bringup')
    navigation_share = get_package_share_directory('turtlebot4_navigation')
    viz_share = get_package_share_directory('turtlebot4_viz')
    package_share = get_package_share_directory('turtlebot_simu')

    arguments = [
        DeclareLaunchArgument('model', default_value='standard', choices=['standard', 'lite']),
        DeclareLaunchArgument('world', default_value='small_room'),
        DeclareLaunchArgument('namespace', default_value=''),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.0'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        DeclareLaunchArgument('sync', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('rviz', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument(
            'check_topics', default_value='true', choices=['true', 'false'],
        ),
    ] + world_launch_arguments()

    simulator = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [simulator_share, 'launch', 'turtlebot4_ignition.launch.py'],
            ),
        ),
        launch_arguments={
            'model': LaunchConfiguration('model'),
            'world': LaunchConfiguration('world'),
            'gz_args': LaunchConfiguration('gz_args'),
            'rviz': 'false',
            # Stop SLAM and the remaining nodes when Gazebo is closed.
            'on_exit_shutdown': 'true',
            'namespace': LaunchConfiguration('namespace'),
            'x': LaunchConfiguration('x'),
            'y': LaunchConfiguration('y'),
            'z': LaunchConfiguration('z'),
            'yaw': LaunchConfiguration('yaw'),
        }.items(),
    )

    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([navigation_share, 'launch', 'slam.launch.py']),
        ),
        launch_arguments={
            'use_sim_time': 'true',
            'sync': LaunchConfiguration('sync'),
            'namespace': LaunchConfiguration('namespace'),
            'params': PathJoinSubstitution([package_share, 'config', 'slam.yaml']),
        }.items(),
    )

    rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([viz_share, 'launch', 'view_robot.launch.py']),
        ),
        launch_arguments={
            'use_sim_time': 'true',
            'namespace': LaunchConfiguration('namespace'),
        }.items(),
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    delayed_check = TimerAction(
        period=20.0,
        actions=[
            Node(
                package='turtlebot_simu',
                executable='topic_check',
                namespace=LaunchConfiguration('namespace'),
                output='screen',
                arguments=['--timeout', '90'],
                condition=IfCondition(LaunchConfiguration('check_topics')),
            ),
        ],
    )

    local_dds = SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1')

    return LaunchDescription(arguments + [
        local_dds, GroupAction([simulator]), GroupAction([slam]), rviz, delayed_check,
    ])
