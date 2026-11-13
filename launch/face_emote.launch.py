"""Start the simulator and webcam emotion recognition together."""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    root = get_package_share_directory('ttbot4_face_emote')
    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=os.path.join(root, 'config', 'emotions.yaml')),
        DeclareLaunchArgument('headless', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('recognition', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('camera_index', default_value='0'),
        DeclareLaunchArgument('show_camera', default_value='true', choices=['true', 'false']),
        # Keep the simulation's command topics local to this machine.
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(root, 'launch', 'simulation.launch.py')),
            launch_arguments={'headless': LaunchConfiguration('headless')}.items()),
        Node(package='ttbot4_face_emote', executable='face_emote', name='face_emote',
             output='screen', condition=IfCondition(LaunchConfiguration('recognition')),
             parameters=[LaunchConfiguration('params_file'), {
                 'use_sim_time': False,
                 'cmd_vel_topic': '/cmd_vel',
                 'camera_index': ParameterValue(LaunchConfiguration('camera_index'), value_type=int),
                 'show_camera': ParameterValue(LaunchConfiguration('show_camera'), value_type=bool),
             }]),
    ])
