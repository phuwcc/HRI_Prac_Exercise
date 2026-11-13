from glob import glob
from setuptools import find_packages, setup

package = 'ttbot4_face_emote'
setup(
    name=package, version='1.0.0', packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package]),
        ('share/' + package, ['package.xml', 'README.md', 'requirements.txt', 'bai8.txt']),
        ('share/' + package + '/launch', glob('launch/*.launch.py')),
        ('share/' + package + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Phuc', maintainer_email='phuc@example.com', license='Apache-2.0',
    description='Webcam facial expressions controlling TurtleBot through ROS 2.',
    entry_points={'console_scripts': ['face_emote = ttbot4_face_emote.node:main']},
)
