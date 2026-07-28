from glob import glob
from setuptools import find_packages, setup

package_name = 'buddy_gazebo'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*')),
        ('share/' + package_name + '/worlds', glob('worlds/*')),
        ('share/' + package_name + '/models/buddy', glob('models/buddy/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Buddy maintainers',
    maintainer_email='maintainers@example.com',
    description='Gazebo Harmonic simulation support for Buddy.',
    license='Apache-2.0',
    test_suite='test.test_model',
    entry_points={'console_scripts': ['safe_cmd_vel_adapter = buddy_gazebo.safe_cmd_vel_adapter:main']},
)
