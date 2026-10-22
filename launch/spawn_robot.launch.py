"""Spawn TurtleBot 4 directly on the floor, without a charging dock."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory as share
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def include(package, filename, **arguments):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(Path(share(package), 'launch', filename))),
        launch_arguments=arguments.items(),
    )


def generate_launch_description():
    model = LaunchConfiguration('model')
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value='lite', choices=['lite', 'standard']),
        include('turtlebot4_description', 'robot_description.launch.py',
                model=model, robot_name='turtlebot4', namespace='', use_sim_time='true'),
        Node(package='ros_ign_gazebo', executable='create', output='screen',
             arguments=['-name', 'turtlebot4', '-x', '0', '-y', '0', '-z', '0.01',
                        '-Y', '0', '-topic', 'robot_description']),
        include('turtlebot4_ignition_bringup', 'ros_ign_bridge.launch.py',
                model=model, robot_name='turtlebot4', namespace='',
                world='gesture_arena', use_sim_time='true'),
        include('turtlebot4_ignition_bringup', 'turtlebot4_nodes.launch.py', model=model),
        include('irobot_create_common_bringup', 'create3_nodes.launch.py', namespace=''),
        include('irobot_create_ignition_bringup', 'create3_ignition_nodes.launch.py',
                robot_name='turtlebot4'),
        Node(package='tf2_ros', executable='static_transform_publisher', name='rplidar_stf',
             arguments=['0', '0', '0', '0', '0', '0',
                        'rplidar_link', 'turtlebot4/rplidar_link/rplidar']),
        Node(package='tf2_ros', executable='static_transform_publisher', name='camera_stf',
             arguments=['0', '0', '0', '1.5707', '-1.5707', '0',
                        'oakd_rgb_camera_optical_frame',
                        'turtlebot4/oakd_rgb_camera_frame/rgbd_camera']),
    ])
