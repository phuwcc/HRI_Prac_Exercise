"""Launch simulation, AMCL localization, Nav2 and RViz using a saved map."""

from pathlib import Path
import math

import yaml

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    OpaqueFunction,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution


def validate_map(context):
    """Reject missing maps and the starter asset before starting the simulator."""
    path = Path(LaunchConfiguration('map').perform(context)).expanduser()
    try:
        text = path.read_text(encoding='utf-8')
        config = yaml.safe_load(text)
        if not isinstance(config, dict) or not isinstance(config.get('image'), str):
            raise ValueError('Map YAML must contain an image path.')
        image = path.parent / config['image']
        if not image.is_file():
            raise ValueError(f'Map image does not exist: {image}')
        with image.open('rb') as stream:
            header = stream.read(256)
        if 'STARTER MAP ONLY' in text or b'STARTER MAP ONLY' in header:
            raise ValueError('The bundled map is a starter map; save a real SLAM map first.')
        resolution = config.get('resolution')
        origin = config.get('origin')
        free = config.get('free_thresh')
        occupied = config.get('occupied_thresh')
        def numeric(value):
            return (
                isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value)
            )
        if not numeric(resolution) or resolution <= 0:
            raise ValueError('Map resolution must be finite and positive.')
        if not isinstance(origin, list) or len(origin) != 3 or not all(map(numeric, origin)):
            raise ValueError('Map origin must contain three finite numbers.')
        if not numeric(free) or not numeric(occupied) or not 0 <= free < occupied <= 1:
            raise ValueError('Map thresholds must satisfy 0 <= free_thresh < occupied_thresh <= 1.')
        if config.get('negate') not in (0, 1):
            raise ValueError('Map negate must be 0 or 1.')
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise RuntimeError(f'Cannot use map {path}: {error}') from error
    return []


def generate_launch_description() -> LaunchDescription:
    simulator_share = get_package_share_directory('turtlebot4_ignition_bringup')
    navigation_share = get_package_share_directory('turtlebot4_navigation')
    package_share = get_package_share_directory('turtlebot_simu')
    viz_share = get_package_share_directory('turtlebot4_viz')

    arguments = [
        DeclareLaunchArgument('model', default_value='standard', choices=['standard', 'lite']),
        DeclareLaunchArgument('world', default_value='maze'),
        DeclareLaunchArgument('namespace', default_value=''),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.0'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        DeclareLaunchArgument('rviz', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument(
            'map',
            default_value=PathJoinSubstitution([package_share, 'maps', 'map.yaml']),
            description='Absolute path to the map YAML produced during mapping.',
        ),
    ]

    simulator = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [simulator_share, 'launch', 'turtlebot4_ignition.launch.py'],
            ),
        ),
        launch_arguments={
            'model': LaunchConfiguration('model'),
            'world': LaunchConfiguration('world'),
            'rviz': 'false',
            # Stop Nav2 and the remaining nodes when Gazebo is closed.
            'on_exit_shutdown': 'true',
            'namespace': LaunchConfiguration('namespace'),
            'x': LaunchConfiguration('x'),
            'y': LaunchConfiguration('y'),
            'z': LaunchConfiguration('z'),
            'yaw': LaunchConfiguration('yaw'),
        }.items(),
    )

    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([navigation_share, 'launch', 'localization.launch.py']),
        ),
        launch_arguments={
            'use_sim_time': 'true',
            'namespace': LaunchConfiguration('namespace'),
            'map': LaunchConfiguration('map'),
            'params': PathJoinSubstitution([navigation_share, 'config', 'localization.yaml']),
        }.items(),
    )

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([navigation_share, 'launch', 'nav2.launch.py']),
        ),
        launch_arguments={
            'use_sim_time': 'true',
            'namespace': LaunchConfiguration('namespace'),
            'params_file': PathJoinSubstitution([package_share, 'config', 'nav2.yaml']),
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

    local_dds = SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1')

    return LaunchDescription(arguments + [
        local_dds, OpaqueFunction(function=validate_map),
        GroupAction([simulator]), GroupAction([localization]),
        GroupAction([nav2]), rviz,
    ])
