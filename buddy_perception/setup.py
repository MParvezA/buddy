from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'buddy_perception'

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
    description='Minimal raw-sensor readiness boundary for Buddy perception.',
    license='Proprietary',
    entry_points={
        'console_scripts': [
            'sensor_readiness = buddy_perception.sensor_readiness:main',
        ],
    },
)
