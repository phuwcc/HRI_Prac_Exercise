from glob import glob
from setuptools import find_packages, setup

setup(
    name='ttbot4_seman_nav', version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/ttbot4_seman_nav']),
        ('share/ttbot4_seman_nav', ['package.xml', 'README.md']),
        ('share/ttbot4_seman_nav/launch', glob('launch/*.launch.py')),
        ('share/ttbot4_seman_nav/config', glob('config/*')),
    ],
    install_requires=['setuptools'], extras_require={'test': ['pytest>=7,<9']}, zip_safe=True,
    maintainer='Student', maintainer_email='student@example.com',
    description='Semantic map segmentation and Vietnamese voice navigation for TurtleBot 4.',
    license='Apache-2.0',
    entry_points={'console_scripts': [
        'segment_map = ttbot4_seman_nav.segmentation:main',
        'voice_navigation = ttbot4_seman_nav.navigation:main',
        'speech_recognition = ttbot4_seman_nav.speech:main',
    ]},
)
