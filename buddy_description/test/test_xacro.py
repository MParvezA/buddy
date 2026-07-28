#!/usr/bin/env python3
"""Validate the configurable robot description without a GUI."""
import subprocess
import sys
import xml.etree.ElementTree as ET

xacro, model = sys.argv[1:]
rendered = subprocess.check_output([xacro, model], text=True)
root = ET.fromstring(rendered)
links = {node.attrib['name'] for node in root.findall('link')}
joints = {node.attrib['name'] for node in root.findall('joint')}
required_links = {'base_link', 'base_footprint', 'left_wheel_link', 'right_wheel_link',
                  'caster_link', 'lidar_link', 'imu_link', 'camera_link', 'camera_optical_frame'}
required_joints = {'left_wheel_joint', 'right_wheel_joint'}
assert required_links <= links, required_links - links
assert required_joints <= joints, required_joints - joints
assert len(root.findall(".//inertial")) >= 4
