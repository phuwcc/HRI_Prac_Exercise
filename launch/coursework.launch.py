"""Run the complete localization, Nav2, three-goal, and YOLO exercise."""

import math
from pathlib import Path

from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    EmitEvent,
    GroupAction,
    IncludeLaunchDescription,
    OpaqueFunction,
    RegisterEventHandler,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, PushRosNamespace, SetRemap
from launch_ros.parameter_descriptions import ParameterValue
import yaml

from ttbot4_nav_detect.launch_support import detector_environment, world_launch_arguments


def validate_map(context):
    """Fail early when map YAML or its image is invalid."""
    path = Path(LaunchConfiguration('map').perform(context)).expanduser()
    try:
        config = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(config, dict) or not isinstance(config.get('image'), str):
            raise ValueError('map YAML must contain an image path')
        if not (path.parent / config['image']).is_file():
            raise ValueError(f'map image does not exist: {path.parent / config["image"]}')

        def numeric(value):
            return (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
            )

        if not numeric(config.get('resolution')) or config['resolution'] <= 0:
            raise ValueError('resolution must be finite and positive')
        origin = config.get('origin')
        if not isinstance(origin, list) or len(origin) != 3 or not all(map(numeric, origin)):
            raise ValueError('origin must contain three finite numbers')
        free = config.get('free_thresh')
        occupied = config.get('occupied_thresh')
        if not numeric(free) or not numeric(occupied) or not 0 <= free < occupied <= 1:
            raise ValueError('thresholds must satisfy 0 <= free_thresh < occupied_thresh <= 1')
        if config.get('negate') not in (0, 1):
            raise ValueError('negate must be 0 or 1')
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise RuntimeError(f'Cannot use map {path}: {error}') from error
    return []


def validate_middleware(_context):
    try:
        get_package_share_directory('rmw_cyclonedds_cpp')
    except PackageNotFoundError as error:
        raise RuntimeError(
            'Install Cyclone DDS first: sudo apt install ros-humble-rmw-cyclonedds-cpp',
        ) from error
    return []


def generate_launch_description():
    simulator_share = get_package_share_directory('turtlebot4_ignition_bringup')
    navigation_share = get_package_share_directory('turtlebot4_navigation')
    nav2_share = get_package_share_directory('nav2_bringup')
    package_share = get_package_share_directory('ttbot4_nav_detect')

    arguments = [
        DeclareLaunchArgument('model', default_value='standard', choices=['standard', 'lite']),
        DeclareLaunchArgument('world', default_value='small_room'),
        DeclareLaunchArgument('namespace', default_value=''),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.0'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        DeclareLaunchArgument('rviz', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('detect', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('run_mission', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('auto_undock', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument(
            'auto_initial_pose', default_value='true', choices=['true', 'false'],
        ),
        DeclareLaunchArgument('initial_x', default_value='0.0'),
        DeclareLaunchArgument('initial_y', default_value='0.0'),
        DeclareLaunchArgument('initial_yaw', default_value='0.0'),
        DeclareLaunchArgument('localization_timeout', default_value='180.0'),
        DeclareLaunchArgument('image_topic', default_value='/oakd/rgb/preview/image_raw'),
        DeclareLaunchArgument('annotated_topic', default_value='/yolo/annotated_image'),
        DeclareLaunchArgument('yolo_model', default_value='yolov8n.pt'),
        DeclareLaunchArgument('confidence', default_value='0.40'),
        DeclareLaunchArgument('inference_hz', default_value='5.0'),
        DeclareLaunchArgument('show_window', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument(
            'map',
            default_value=PathJoinSubstitution([package_share, 'maps', 'small_room.yaml']),
        ),
        DeclareLaunchArgument(
            'goals_file',
            default_value=PathJoinSubstitution(
                [package_share, 'config', 'waypoints_small_room.yaml'],
            ),
        ),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=PathJoinSubstitution([package_share, 'config', 'navigation.rviz']),
        ),
    ] + world_launch_arguments(headless_default='true')

    simulator = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            simulator_share, 'launch', 'turtlebot4_ignition.launch.py',
        ])),
        launch_arguments={
            'model': LaunchConfiguration('model'),
            'world': LaunchConfiguration('world'),
            'gz_args': LaunchConfiguration('gz_args'),
            'rviz': 'false',
            'on_exit_shutdown': 'true',
            'namespace': LaunchConfiguration('namespace'),
            'x': LaunchConfiguration('x'),
            'y': LaunchConfiguration('y'),
            'z': LaunchConfiguration('z'),
            'yaw': LaunchConfiguration('yaw'),
        }.items(),
    )

    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            navigation_share, 'launch', 'localization.launch.py',
        ])),
        launch_arguments={
            'use_sim_time': 'true',
            'namespace': LaunchConfiguration('namespace'),
            'map': LaunchConfiguration('map'),
            'params': PathJoinSubstitution([package_share, 'config', 'localization.yaml']),
        }.items(),
    )

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            nav2_share, 'launch', 'navigation_launch.py',
        ])),
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

    detector = Node(
        package='ttbot4_nav_detect',
        executable='object_detector',
        name='object_detector',
        namespace=LaunchConfiguration('namespace'),
        output='screen',
        additional_env=detector_environment(),
        parameters=[{
            'use_sim_time': True,
            'image_topic': LaunchConfiguration('image_topic'),
            'annotated_topic': LaunchConfiguration('annotated_topic'),
            'model': LaunchConfiguration('yolo_model'),
            'confidence': ParameterValue(LaunchConfiguration('confidence'), value_type=float),
            'inference_hz': ParameterValue(LaunchConfiguration('inference_hz'), value_type=float),
            'show_window': ParameterValue(LaunchConfiguration('show_window'), value_type=bool),
        }],
        condition=IfCondition(LaunchConfiguration('detect')),
    )

    ready = Node(
        package='ttbot4_nav_detect',
        executable='navigation_ready',
        namespace=LaunchConfiguration('namespace'),
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'auto_initial_pose': ParameterValue(
                LaunchConfiguration('auto_initial_pose'), value_type=bool,
            ),
            'initial_x': ParameterValue(LaunchConfiguration('initial_x'), value_type=float),
            'initial_y': ParameterValue(LaunchConfiguration('initial_y'), value_type=float),
            'initial_yaw': ParameterValue(LaunchConfiguration('initial_yaw'), value_type=float),
            'timeout': ParameterValue(
                LaunchConfiguration('localization_timeout'), value_type=float,
            ),
        }],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
    )

    mission = Node(
        package='ttbot4_nav_detect',
        executable='waypoint_mission',
        namespace=LaunchConfiguration('namespace'),
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'goals_file': LaunchConfiguration('goals_file'),
            'auto_undock': ParameterValue(LaunchConfiguration('auto_undock'), value_type=bool),
        }],
        condition=IfCondition(LaunchConfiguration('run_mission')),
    )

    def start_nav2(event, context):
        if event.returncode != 0:
            return [EmitEvent(event=Shutdown(
                reason='Localization did not become ready; see navigation_ready log.',
            ))]
        namespace = LaunchConfiguration('namespace').perform(context).strip('/')
        prefix = '/' + namespace if namespace else ''
        return [GroupAction([
            PushRosNamespace(LaunchConfiguration('namespace')),
            SetRemap(prefix + '/global_costmap/scan', prefix + '/scan'),
            SetRemap(prefix + '/local_costmap/scan', prefix + '/scan'),
            Node(
                package='rclcpp_components',
                executable='component_container_isolated',
                name='nav2_container',
                output='screen',
                parameters=[{'use_sim_time': True}],
                remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
            ),
            nav2,
            TimerAction(period=3.0, actions=[mission]),
        ])]

    start_after_localization = RegisterEventHandler(
        OnProcessExit(target_action=ready, on_exit=start_nav2),
    )

    return LaunchDescription(arguments + [
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1'),
        SetEnvironmentVariable('RMW_IMPLEMENTATION', 'rmw_cyclonedds_cpp'),
        SetEnvironmentVariable(
            'CYCLONEDDS_URI',
            ['file://', PathJoinSubstitution([package_share, 'config', 'cyclonedds.xml'])],
        ),
        OpaqueFunction(function=validate_middleware),
        OpaqueFunction(function=validate_map),
        GroupAction([simulator]),
        GroupAction([localization]),
        detector,
        start_after_localization,
        ready,
        rviz,
    ])
