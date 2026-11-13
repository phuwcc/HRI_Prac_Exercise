"""TurtleBot 4 Lite on a local Gazebo Fortress floor, without docking."""
import os
from pathlib import Path
import shlex

from ament_index_python.packages import get_package_share_directory as share
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            RegisterEventHandler, SetEnvironmentVariable)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    root = Path(share('ttbot4_face_emote'))
    resources = os.pathsep.join([
        str(Path(share('turtlebot4_description')).parent),
        str(Path(share('irobot_create_description')).parent),
        os.environ.get('IGN_GAZEBO_RESOURCE_PATH', ''),
    ])
    spawn = Node(package='ros_gz_sim', executable='create', output='screen',
                 arguments=['-world', 'emotion_arena', '-name', 'turtlebot4',
                            '-x', '0', '-y', '0', '-z', '0.02',
                            '-topic', 'robot_description'])
    joints = Node(package='controller_manager', executable='spawner', output='screen',
                  arguments=['joint_state_broadcaster', '-c', '/controller_manager',
                             '--controller-manager-timeout', '120'])
    drive = Node(package='controller_manager', executable='spawner', output='screen',
                 arguments=['diffdrive_controller', '-c', '/controller_manager',
                            '--controller-manager-timeout', '120'])
    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='false', choices=['true', 'false']),
        SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', resources),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(Path(share('ros_gz_sim'), 'launch', 'gz_sim.launch.py'))),
            launch_arguments={'gz_args': [
                shlex.quote(str(root / 'worlds' / 'emotion_arena.sdf')), ' -r -v 2',
                PythonExpression(["' -s --headless-rendering' if '",
                                  LaunchConfiguration('headless'), "' == 'true' else ''"]),
            ], 'on_exit_shutdown': 'true'}.items()),
        # Only the simulated wheel hardware publishes joint states.
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             output='screen', parameters=[{'use_sim_time': True,
                 'robot_description': ParameterValue(Command([
                     'xacro ', str(Path(share('turtlebot4_description'), 'urdf',
                                        'lite', 'turtlebot4.urdf.xacro')),
                     ' gazebo:=ignition']), value_type=str)}]),
        RegisterEventHandler(OnProcessExit(target_action=spawn, on_exit=[joints])),
        RegisterEventHandler(OnProcessExit(target_action=joints, on_exit=[drive])),
        spawn,
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='clock_bridge',
             arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock']),
        Node(package='ttbot4_face_emote', executable='sim_velocity_relay', output='screen'),
    ])
