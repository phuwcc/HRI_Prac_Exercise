"""Launch simulation, AMCL localization, Nav2 and RViz using a saved map."""

from pathlib import Path
import math

import yaml

from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    OpaqueFunction,
    SetEnvironmentVariable,
    RegisterEventHandler,
    EmitEvent,
)
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, PushRosNamespace, SetRemap
from launch_ros.parameter_descriptions import ParameterValue
from turtlebot_simu.launch_support import world_launch_arguments


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


def validate_middleware(context):
    """Fail before spawning Gazebo when the required middleware is missing."""
    try:
        get_package_share_directory('rmw_cyclonedds_cpp')
    except PackageNotFoundError as error:
        raise RuntimeError(
            'Navigation requires Cyclone DDS. Install it once with: '
            'sudo apt install ros-humble-rmw-cyclonedds-cpp'
        ) from error
    return []


def generate_launch_description() -> LaunchDescription:
    simulator_share = get_package_share_directory('turtlebot4_ignition_bringup')
    navigation_share = get_package_share_directory('turtlebot4_navigation')
    nav2_share = get_package_share_directory('nav2_bringup')
    package_share = get_package_share_directory('turtlebot_simu')

    arguments = [
        DeclareLaunchArgument('model', default_value='lite', choices=['standard', 'lite']),
        DeclareLaunchArgument('world', default_value='small_room'),
        DeclareLaunchArgument('namespace', default_value=''),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.0'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        DeclareLaunchArgument('rviz', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('auto_initial_pose', default_value='true', choices=['true', 'false'],
                             description='Seed AMCL once; initial coordinates are in map, not world.'),
        DeclareLaunchArgument('initial_x', default_value='0.0'),
        DeclareLaunchArgument('initial_y', default_value='0.0'),
        DeclareLaunchArgument('initial_yaw', default_value='0.0'),
        DeclareLaunchArgument('localization_timeout', default_value='180.0'),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=PathJoinSubstitution([package_share, 'config', 'navigation.rviz']),
            description='RViz configuration; the package default is optimized for low load.',
        ),
        DeclareLaunchArgument(
            'map',
            default_value=PathJoinSubstitution([package_share, 'maps', 'small_room.yaml']),
            description='Absolute path to the map YAML produced during mapping.',
        ),
    ] + world_launch_arguments(headless_default='true')

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
            'params': PathJoinSubstitution([package_share, 'config', 'localization.yaml']),
        }.items(),
    )

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([nav2_share, 'launch', 'navigation_launch.py']),
        ),
        launch_arguments={
            'use_sim_time': 'true',
            'namespace': LaunchConfiguration('namespace'),
            'params_file': PathJoinSubstitution([package_share, 'config', 'nav2.yaml']),
            'use_composition': 'True',
            'container_name': 'nav2_container',
        }.items(),
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        namespace=LaunchConfiguration('namespace'),
        arguments=['-d', LaunchConfiguration('rviz_config')],
        parameters=[{'use_sim_time': True}],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
        output='screen',
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    local_dds = SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1')
    middleware = SetEnvironmentVariable('RMW_IMPLEMENTATION', 'rmw_cyclonedds_cpp')
    discovery = SetEnvironmentVariable(
        'CYCLONEDDS_URI', ['file://', PathJoinSubstitution([package_share, 'config', 'cyclonedds.xml'])],
    )

    ready = Node(
        package='turtlebot_simu', executable='navigation_ready',
        namespace=LaunchConfiguration('namespace'), output='screen',
        parameters=[{
            'use_sim_time': True,
            'auto_initial_pose': ParameterValue(LaunchConfiguration('auto_initial_pose'), value_type=bool),
            'initial_x': ParameterValue(LaunchConfiguration('initial_x'), value_type=float),
            'initial_y': ParameterValue(LaunchConfiguration('initial_y'), value_type=float),
            'initial_yaw': ParameterValue(LaunchConfiguration('initial_yaw'), value_type=float),
            'timeout': ParameterValue(LaunchConfiguration('localization_timeout'), value_type=float),
        }],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
    )

    def start_nav2(event, context):
        if event.returncode == 0:
            namespace = LaunchConfiguration('namespace').perform(context).strip('/')
            prefix = '/' + namespace if namespace else ''
            return [GroupAction([
                PushRosNamespace(LaunchConfiguration('namespace')),
                SetRemap(prefix + '/global_costmap/scan', prefix + '/scan'),
                SetRemap(prefix + '/local_costmap/scan', prefix + '/scan'),
                Node(
                    package='rclcpp_components', executable='component_container_isolated',
                    name='nav2_container', output='screen',
                    parameters=[{'use_sim_time': True}],
                    remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                ),
                nav2,
            ])]
        return [EmitEvent(event=Shutdown(reason='Localization did not become ready; see navigation_ready log.'))]

    start_after_localization = RegisterEventHandler(
        OnProcessExit(target_action=ready, on_exit=start_nav2),
    )

    return LaunchDescription(arguments + [
        local_dds, middleware, discovery,
        OpaqueFunction(function=validate_middleware), OpaqueFunction(function=validate_map),
        GroupAction([simulator]), GroupAction([localization]),
        start_after_localization, ready, rviz,
    ])
