from setuptools import find_packages, setup


package_name = 'buddy_capabilities'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    test_suite='test',
    zip_safe=True,
    maintainer='Parvez',
    maintainer_email='mohamedparvez27@gmail.com',
    description='Capability schema registry for Buddy task execution.',
    license='Proprietary',
    entry_points={'console_scripts': [
        'capability_registry = buddy_capabilities.registry:main',
    ]},
)
