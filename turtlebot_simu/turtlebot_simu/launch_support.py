"""Resolve package-local worlds without changing upstream simulator packages."""

from pathlib import Path
import shlex

from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetLaunchConfiguration
from launch.substitutions import LaunchConfiguration


def configure_gazebo(context):
    """Use an absolute SDF path while keeping the world name for sensor bridges."""
    if LaunchConfiguration('gz_args').perform(context):
        return []
    world = LaunchConfiguration('world').perform(context)
    headless = LaunchConfiguration('headless').perform(context) == 'true'
    if world != 'small_room' and not headless:
        return []  # Keep the upstream launch behavior for its built-in worlds.
    package = 'turtlebot_simu' if world == 'small_room' else 'turtlebot4_ignition_bringup'
    path = Path(get_package_share_directory(package), 'worlds', f'{world}.sdf')
    if not path.is_file():
        raise RuntimeError(f'Gazebo world does not exist: {path}')
    arguments = [str(path), '-r', '-v', '2']
    if headless:
        arguments.extend(['-s', '--headless-rendering'])
    else:
        model = LaunchConfiguration('model').perform(context)
        gui = Path(get_package_share_directory('turtlebot4_ignition_bringup'),
                   'gui', model, 'gui.config')
        arguments.extend(['--gui-config', str(gui)])
    return [SetLaunchConfiguration('gz_args', shlex.join(arguments))]


def world_launch_arguments():
    return [
        DeclareLaunchArgument('headless', default_value='false', choices=['true', 'false'],
                             description='Run Gazebo server without its GUI.'),
        DeclareLaunchArgument('gz_args', default_value='',
                             description='Optional complete Gazebo command-line override.'),
        OpaqueFunction(function=configure_gazebo),
    ]
