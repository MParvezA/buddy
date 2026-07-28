from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'buddy_navigation'

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
    install_requires=['setuptools'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='Parvez',
    maintainer_email='mohamedparvez27@gmail.com',
    description='Named-location adapter and bounded Nav2 configuration for Buddy.',
    license='Proprietary',
    entry_points={
        'console_scripts': [
            'named_navigation_adapter = '
            'buddy_navigation.named_navigation_adapter:main',
            'velocity_boundary = buddy_navigation.velocity_boundary:main',
        ],
    },
)
