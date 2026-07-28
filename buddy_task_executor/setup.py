from setuptools import find_packages, setup


package_name = 'buddy_task_executor'

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
    description='Validated sequential task execution for Buddy.',
    license='Proprietary',
    entry_points={'console_scripts': [
        'task_executive = buddy_task_executor.executive:main',
    ]},
)
