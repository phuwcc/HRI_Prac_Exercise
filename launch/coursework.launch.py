"""Reuse the workspace simulator/Nav2, adding semantic navigation and speech."""
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction,
                            RegisterEventHandler, SetEnvironmentVariable)
from launch.event_handlers import OnShutdown
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from ttbot4_seman_nav.map_data import load_regions
from ttbot4_seman_nav.navigation_map import write_navigation_map
from ttbot4_seman_nav.runtime import validate_tf2_runtime


def simulator_environment():
    """Give the world, spawn clients and bridges one fresh Transport partition.

    Gazebo can survive a launch shutdown. Reusing its discovery partition may
    connect create/clock bridges to the old server instead of the new world.
    ROS-only clients (command/status/undock) do not need this partition.
    """
    partition = 'semantic_nav_' + uuid4().hex
    return [SetEnvironmentVariable(name, partition)
            for name in ('IGN_PARTITION', 'GZ_PARTITION')]


def start(context):
    regions = LaunchConfiguration('regions').perform(context)
    data, grid = load_regions(regions)
    cleanup = []
    environment = []
    if IfCondition(LaunchConfiguration('navigation')).evaluate(context):
        validate_tf2_runtime()
        environment = simulator_environment()
        if IfCondition(LaunchConfiguration('dock_keepout')).evaluate(context):
            temporary = TemporaryDirectory(prefix='semantic_nav_map_')
            grid = write_navigation_map(grid, temporary.name, *(
                float(LaunchConfiguration(key).perform(context))
                for key in ('initial_x', 'initial_y', 'initial_yaw')))
            for region in data['regions']:
                goal = region['goal']
                if not grid.safe(float(goal['x']), float(goal['y']), data['clearance']):
                    raise ValueError(f'Region {region["id"]} overlaps the dock keepout.')

            def remove_map(context):
                temporary.cleanup()
                return []

            cleanup = [RegisterEventHandler(OnShutdown(
                on_shutdown=[OpaqueFunction(function=remove_map)]))]
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
    return [*environment, *cleanup, nav, Node(
        package='ttbot4_seman_nav', executable='voice_navigation', output='screen',
        parameters=[{'regions_file': regions, 'use_sim_time': True}],
    ), Node(
        package='ttbot4_seman_nav', executable='speech_recognition', output='screen',
        condition=IfCondition(LaunchConfiguration('speech')),
        parameters=[{
            'model': LaunchConfiguration('whisper_model'), 'device': 'cpu',
            'language': 'en',
            'microphone': ParameterValue(LaunchConfiguration('microphone'), value_type=str),
        }],
    )]


def generate_launch_description():
    arguments = [DeclareLaunchArgument('regions', description='Absolute path to generated regions.yaml')]
    for name, default in {
        'navigation': 'true', 'speech': 'true', 'whisper_model': 'base.en',
        'microphone': '',
        'dock_keepout': 'true',
        'world': 'small_room', 'headless': 'true', 'rviz': 'true',
        'auto_initial_pose': 'true', 'initial_x': '0.0', 'initial_y': '0.0', 'initial_yaw': '0.0',
    }.items():
        arguments.append(DeclareLaunchArgument(name, default_value=default))
    return LaunchDescription(arguments + [OpaqueFunction(function=start)])
