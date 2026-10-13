from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'turtlebot_simu'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
        (os.path.join('share', package_name, 'maps'), glob('maps/*')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
        (os.path.join('share', package_name, 'docs'), glob('docs/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Student',
    maintainer_email='student@example.com',
    description='TurtleBot 4 simulation, SLAM, localization and Nav2 coursework package.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'save_map = turtlebot_simu.save_map:main',
            'topic_check = turtlebot_simu.topic_check:main',
            'waypoint_nav = turtlebot_simu.waypoint_nav:main',
        ],
    },
)
