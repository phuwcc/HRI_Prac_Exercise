"""One launch for Gazebo, webcam recognition, and gesture-controlled behaviors."""

import os
from pathlib import Path
import shlex
import sys

from ament_index_python.packages import get_package_share_directory as share
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, EmitEvent, IncludeLaunchDescription,
                            OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration as Config
from launch.substitutions import PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def recognition_environment():
    """Expose Conda's AI dependencies even when colcon uses system Python."""
    prefix = os.environ.get('CONDA_PREFIX')
    if not prefix:
        return {}
    version = f'python{sys.version_info.major}.{sys.version_info.minor}'
    packages = str(Path(prefix, 'lib', version, 'site-packages'))
    paths = [packages, os.environ.get('PYTHONPATH', '')]
    return {'PYTHONPATH': os.pathsep.join(filter(None, paths))}


def start(context):
    root = Path(share('ttbot4_handges_control'))
    model = Path(Config('model_path').perform(context)).expanduser()
    if not model.is_file():
        raise RuntimeError(f'Missing gesture model: {model}. See README section 1.')
    config = str(root / 'config' / 'gestures.yaml')
    behavior = Node(
        package='ttbot4_handges_control', executable='robot_behavior_node',
        output='screen', parameters=[config, {'use_sim_time': False}],
    )
    recognizer = Node(
        package='ttbot4_handges_control', executable='gesture_recognition_node',
        output='screen', additional_env=recognition_environment(),
        parameters=[config, {
            'use_sim_time': False, 'model_path': str(model),
            'camera_index': ParameterValue(Config('camera_index'), value_type=int),
            'show_window': ParameterValue(Config('show_window'), value_type=bool),
        }],
    )
    actions = []
    for node in (behavior, recognizer):
        actions.append(RegisterEventHandler(OnProcessExit(
            target_action=node,
            on_exit=[EmitEvent(event=Shutdown(reason='A gesture control node exited.'))],
        )))
    return actions + [behavior, recognizer]


def generate_launch_description():
    root = Path(share('ttbot4_handges_control'))
    simulator = Path(share('turtlebot4_ignition_bringup'))
    resource_path = os.pathsep.join([
        str(root / 'worlds'), str(simulator / 'worlds'),
        str(Path(share('irobot_create_ignition_bringup')) / 'worlds'),
        str(Path(share('turtlebot4_description')).parent),
        str(Path(share('irobot_create_description')).parent),
        os.environ.get('IGN_GAZEBO_RESOURCE_PATH', ''),
    ])
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(Path(share('ros_ign_gazebo')) /
                                         'launch' / 'ign_gazebo.launch.py')),
        launch_arguments={'ign_args': [
            shlex.quote(str(root / 'worlds' / 'gesture_arena.sdf')), ' -r -v 2',
            PythonExpression(["' -s --headless-rendering' if '", Config('headless'),
                              "' == 'true' else ''"]),
        ], 'on_exit_shutdown': 'true'}.items(),
        condition=IfCondition(Config('simulation')),
    )
    spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(root / 'launch' / 'spawn_robot.launch.py')),
        launch_arguments={'model': Config('model')}.items(),
        condition=IfCondition(Config('simulation')),
    )
    return LaunchDescription([
        DeclareLaunchArgument('simulation', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('model', default_value='lite', choices=['lite', 'standard']),
        DeclareLaunchArgument('headless', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('camera_index', default_value='0'),
        DeclareLaunchArgument('show_window', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('model_path', default_value=str(
            Path.home() / '.cache' / 'mediapipe' / 'gesture_recognizer.task')),
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1'),
        SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', resource_path),
        # Validate the model before starting the expensive simulator.
        OpaqueFunction(function=start),
        gazebo, spawn,
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='clock_bridge',
             arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'],
             condition=IfCondition(Config('simulation'))),
    ])
