from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'buddy_world_model'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools', 'PyYAML'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='Parvez',
    maintainer_email='mohamedparvez27@gmail.com',
    description='Bounded semantic named-location and world-summary service for Buddy.',
    license='Proprietary',
    entry_points={
        'console_scripts': [
            'world_model_node = buddy_world_model.world_model_node:main',
        ],
    },
)
