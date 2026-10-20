"""Helpers for resolving the package-local Gazebo world."""

import os
from pathlib import Path
import shlex
import sys

from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetLaunchConfiguration
from launch.substitutions import LaunchConfiguration


def detector_environment(environment=None):
    """Expose the active Conda packages to the ROS Python detector only."""
    environment = os.environ if environment is None else environment
    prefix = environment.get('CONDA_PREFIX', '')
    if not prefix:
        return {}

    version = f'python{sys.version_info.major}.{sys.version_info.minor}'
    site_packages = str(Path(prefix, 'lib', version, 'site-packages'))
    current = environment.get('PYTHONPATH', '')
    paths = [path for path in current.split(os.pathsep) if path]
    if site_packages in paths:
        paths.remove(site_packages)
    paths.insert(0, site_packages)
    return {'PYTHONPATH': os.pathsep.join(paths)}


def configure_gazebo(context):
    """Translate the small_room logical name into its installed absolute path."""
    if LaunchConfiguration('gz_args').perform(context):
        return []
    world = LaunchConfiguration('world').perform(context)
    headless = LaunchConfiguration('headless').perform(context) == 'true'
    if world != 'small_room' and not headless:
        return []
    package = 'ttbot4_nav_detect' if world == 'small_room' else 'turtlebot4_ignition_bringup'
    path = Path(get_package_share_directory(package), 'worlds', f'{world}.sdf')
    if not path.is_file():
        raise RuntimeError(f'Gazebo world does not exist: {path}')
    arguments = [str(path), '-r', '-v', '2']
    if headless:
        arguments.extend(['-s', '--headless-rendering'])
    else:
        model = LaunchConfiguration('model').perform(context)
        gui = Path(
            get_package_share_directory('turtlebot4_ignition_bringup'),
            'gui', model, 'gui.config',
        )
        arguments.extend(['--gui-config', str(gui)])
    return [SetLaunchConfiguration('gz_args', shlex.join(arguments))]


def world_launch_arguments(headless_default='true'):
    return [
        DeclareLaunchArgument(
            'headless', default_value=headless_default, choices=['true', 'false'],
            description='Run Gazebo server without its GUI.',
        ),
        DeclareLaunchArgument(
            'gz_args', default_value='',
            description='Optional complete Gazebo command-line override.',
        ),
        OpaqueFunction(function=configure_gazebo),
    ]
