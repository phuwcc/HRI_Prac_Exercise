import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(get_package_share_directory('ttbot4_face_emote'),
                          'config', 'emotions.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=config),
        DeclareLaunchArgument('cmd_vel_topic', default_value='/cmd_vel'),
        Node(package='ttbot4_face_emote', executable='face_emote', name='face_emote',
             output='screen', parameters=[LaunchConfiguration('params_file')],
             remappings=[('/cmd_vel', LaunchConfiguration('cmd_vel_topic'))]),
    ])
