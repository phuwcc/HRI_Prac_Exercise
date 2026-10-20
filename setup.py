from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'ttbot4_nav_detect'

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
    ],
    install_requires=['setuptools'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='Student',
    maintainer_email='student@example.com',
    description='TurtleBot 4 autonomous navigation and YOLO object detection coursework.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'navigation_ready = ttbot4_nav_detect.navigation_ready:main',
            'object_detector = ttbot4_nav_detect.object_detector:main',
            'waypoint_mission = ttbot4_nav_detect.waypoint_mission:main',
        ],
    },
)
