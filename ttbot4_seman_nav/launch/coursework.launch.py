"""Reuse the workspace simulator/Nav2, adding semantic navigation and speech."""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from ttbot4_seman_nav.map_data import load_regions


def start(context):
    regions = LaunchConfiguration('regions').perform(context)
    data, grid = load_regions(regions)
    share = get_package_share_directory('turtlebot_simu')
    nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(Path(share)/'launch/navigation.launch.py')),
        condition=IfCondition(LaunchConfiguration('navigation')),
        launch_arguments={
            'map': str(grid.path),
            **{key: LaunchConfiguration(key) for key in (
                'world', 'headless', 'rviz', 'auto_initial_pose',
                'initial_x', 'initial_y', 'initial_yaw')},
        }.items(),
    )
    return [nav, Node(
        package='ttbot4_seman_nav', executable='voice_navigation', output='screen',
        parameters=[{'regions_file': regions, 'use_sim_time': True}],
    ), Node(
        package='ttbot4_seman_nav', executable='speech_recognition', output='screen',
        condition=IfCondition(LaunchConfiguration('speech')),
        parameters=[{'model': LaunchConfiguration('whisper_model'), 'device': 'cpu'}],
    )]


def generate_launch_description():
    arguments = [DeclareLaunchArgument('regions', description='Absolute path to generated regions.yaml')]
    for name, default in {
        'navigation': 'true', 'speech': 'true', 'whisper_model': 'base',
        'world': 'small_room', 'headless': 'true', 'rviz': 'true',
        'auto_initial_pose': 'true', 'initial_x': '0.0', 'initial_y': '0.0', 'initial_yaw': '0.0',
    }.items():
        arguments.append(DeclareLaunchArgument(name, default_value=default))
    return LaunchDescription(arguments + [OpaqueFunction(function=start)])
