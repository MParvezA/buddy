from setuptools import find_packages, setup


package_name = 'buddy_voice'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/voice.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Parvez',
    maintainer_email='mohamedparvez27@gmail.com',
    description='Local, provider-backed voice input and speech output for Buddy.',
    license='Proprietary',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'voice_input = buddy_voice.voice_node:main',
            'speak_server = buddy_voice.speak_node:main',
        ],
    },
)
