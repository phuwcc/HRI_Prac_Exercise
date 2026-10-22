from glob import glob
from setuptools import find_packages, setup

PACKAGE = 'ttbot4_handges_control'

setup(
    name=PACKAGE,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + PACKAGE]),
        ('share/' + PACKAGE, ['package.xml', 'README.md', 'requirements.txt']),
        ('share/' + PACKAGE + '/launch', glob('launch/*.launch.py')),
        ('share/' + PACKAGE + '/config', glob('config/*.yaml')),
        ('share/' + PACKAGE + '/worlds', glob('worlds/*.sdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Student',
    maintainer_email='student@example.com',
    description='TurtleBot 4 non-verbal interaction with MediaPipe hand gestures.',
    license='Apache-2.0',
    entry_points={'console_scripts': [
        'gesture_recognition_node = ttbot4_handges_control.gesture_recognition_node:main',
        'robot_behavior_node = ttbot4_handges_control.robot_behavior_node:main',
    ]},
)
