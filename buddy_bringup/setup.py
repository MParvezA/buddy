from glob import glob
import os

from setuptools import find_packages, setup


package_name = "buddy_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "launch"),
            glob("launch/*.launch.py"),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Parvez",
    maintainer_email="mohamedparvez27@gmail.com",
    description="Root-owned composition and status supervision for Buddy.",
    license="Proprietary",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "integration_fixture = buddy_bringup.integration_fixture:main",
            "status_supervisor = buddy_bringup.status_supervisor:main",
        ],
    },
)
