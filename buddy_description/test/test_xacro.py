#!/usr/bin/env python3
"""Validate the configurable robot description without a GUI."""
import subprocess
import sys
import xml.etree.ElementTree as ET

xacro, model, *sdf_paths = sys.argv[1:]
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

# Sensor links are positioned by their fixed joint; visual geometry is local.
for sensor_link in ('lidar_link', 'imu_link', 'camera_link'):
    visual_origin = root.find(f"link[@name='{sensor_link}']/visual/origin")
    assert visual_origin is not None
    assert visual_origin.attrib == {'xyz': '0 0 0', 'rpy': '0 0 0'}

if sdf_paths:
    sdf_root = ET.parse(sdf_paths[0]).getroot()
    sdf_model = sdf_root.find('model')
    sdf_links = {node.attrib['name'] for node in sdf_model.findall('link')}
    sdf_frames = {node.attrib['name'] for node in sdf_model.findall('frame')}
    assert required_links <= (sdf_links | sdf_frames), required_links - (sdf_links | sdf_frames)
    sdf_joints = {node.attrib['name'] for node in sdf_model.findall('joint')}
    parity_joints = {'base_footprint_joint', 'left_wheel_joint', 'right_wheel_joint', 'caster_joint'}
    assert parity_joints <= joints
    assert parity_joints <= sdf_joints

    def wheel_radius_urdf(link_name):
        return float(root.find(f"link[@name='{link_name}']/visual/geometry/cylinder").attrib['radius'])

    def wheel_radius_sdf(link_name):
        return float(sdf_model.find(
            f"link[@name='{link_name}']/visual/geometry/cylinder/radius").text)

    for wheel_link in ('left_wheel_link', 'right_wheel_link'):
        assert wheel_radius_urdf(wheel_link) == wheel_radius_sdf(wheel_link) == 0.065
