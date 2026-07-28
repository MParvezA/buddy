"""Fast structural checks for the native Harmonic assets."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


PACKAGE = Path(__file__).resolve().parents[1]


class TestModel(unittest.TestCase):
    def test_model_has_drive_sensors_and_contract_frames(self):
        root = ET.parse(PACKAGE / 'models' / 'buddy' / 'model.sdf').getroot()
        model = root.find('model')
        links = {link.attrib['name'] for link in model.findall('link')}
        self.assertTrue({'base_link', 'base_footprint', 'left_wheel_link', 'right_wheel_link',
                         'caster_link', 'lidar_link', 'imu_link', 'camera_link'} <= links)
        self.assertIsNotNone(model.find(".//joint[@name='left_wheel_joint']"))
        self.assertIsNotNone(model.find(".//joint[@name='right_wheel_joint']"))
        sensor_types = {sensor.attrib['type'] for sensor in model.findall('.//sensor')}
        self.assertTrue({'gpu_lidar', 'imu', 'camera', 'contact'} <= sensor_types)
        plugin_names = {plugin.attrib['name'] for plugin in model.findall('plugin')}
        self.assertIn('gz::sim::systems::DiffDrive', plugin_names)

    def test_bridge_keeps_frozen_sensor_topics(self):
        bridge = (PACKAGE / 'config' / 'bridge.yaml').read_text()
        for topic in ('/clock', '/joint_states', '/odom/wheel', '/scan', '/imu/data_raw',
                      '/camera/image_raw', '/camera/camera_info'):
            self.assertIn(topic, bridge)

    def test_adapter_declares_sim_time_and_restricts_drive_axes(self):
        adapter = (PACKAGE / 'buddy_gazebo' / 'safe_cmd_vel_adapter.py').read_text()
        self.assertIn("has_parameter('use_sim_time')", adapter)
        self.assertIn("declare_parameter('use_sim_time', False)", adapter)
        self.assertIn('message.linear.x = command.twist.linear.x', adapter)
        self.assertIn('message.angular.z = command.twist.angular.z', adapter)
        for forbidden_axis in ('message.linear.y =', 'message.linear.z =',
                               'message.angular.x =', 'message.angular.y ='):
            self.assertNotIn(forbidden_axis, adapter)
