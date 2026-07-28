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
footprint_joint = root.find("joint[@name='base_footprint_joint']")
assert footprint_joint.find('parent').attrib['link'] == 'base_link'
assert footprint_joint.find('child').attrib['link'] == 'base_footprint'
joint_children = [joint.find('child').attrib['link'] for joint in root.findall('joint')]
assert len(joint_children) == len(set(joint_children))
assert 'base_link' not in joint_children

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
    sdf_footprint_joint = sdf_model.find("joint[@name='base_footprint_joint']")
    assert sdf_footprint_joint.findtext('parent') == 'base_link'
    assert sdf_footprint_joint.findtext('child') == 'base_footprint'
    sdf_joint_children = [
        joint.findtext('child') for joint in sdf_model.findall('joint')]
    assert len(sdf_joint_children) == len(set(sdf_joint_children))
    assert 'base_link' not in sdf_joint_children

    def wheel_radius_urdf(link_name):
        return float(root.find(f"link[@name='{link_name}']/visual/geometry/cylinder").attrib['radius'])

    def wheel_radius_sdf(link_name):
        return float(sdf_model.find(
            f"link[@name='{link_name}']/visual/geometry/cylinder/radius").text)

    for wheel_link in ('left_wheel_link', 'right_wheel_link'):
        assert wheel_radius_urdf(wheel_link) == wheel_radius_sdf(wheel_link) == 0.065
