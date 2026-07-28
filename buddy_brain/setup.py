# Copyright 2026 SyncRobot

from setuptools import find_packages, setup


package_name = "buddy_brain"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Parvez",
    maintainer_email="mohamedparvez27@gmail.com",
    description="Bounded local-model dialogue gateway for Buddy.",
    license="Proprietary",
    entry_points={"console_scripts": ["dialogue_node = buddy_brain.dialogue_node:main"]},
)
