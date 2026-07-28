"""Live root-owned voice-to-safe-motion integration test."""

from __future__ import annotations

import json
import os
import threading
import time
import unittest
import uuid

import launch
import launch_ros.actions
import launch_testing.actions
import launch_testing.markers
import pytest
import rclpy
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import TwistStamped
from launch.substitutions import PathJoinSubstitution
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from std_msgs.msg import String

from buddy_interfaces.action import NavigateToNamedLocation
from buddy_interfaces.msg import RecognizedUtterance, RobotStatus


# Keep the probe off the default DDS domain. The launch description explicitly
# propagates the same value to every child below.
TEST_DOMAIN_ID = os.environ.setdefault(
    'ROS_DOMAIN_ID', str(100 + os.getpid() % 100)
)
os.environ.setdefault('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')


MODEL_RESPONSE = json.dumps(
    {
        'kind': 'plan',
        'summary': 'Navigate to home',
        'steps': [
            {
                'capability': 'navigate_to',
                'arguments': {'location': 'home'},
                'timeout_seconds': 10,
                'on_failure': 'abort',
            }
        ],
    },
    separators=(',', ':'),
)


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    """Launch real Buddy layers with only Nav2 and speech replaced by fakes."""
    world_share = get_package_share_directory('buddy_world_model')
    navigation_share = get_package_share_directory('buddy_navigation')
    nodes = [
        launch_ros.actions.Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=[
                '--x', '0', '--y', '0', '--z', '0',
                '--yaw', '0', '--pitch', '0', '--roll', '0',
                '--frame-id', 'map', '--child-frame-id', 'odom',
            ],
        ),
        launch_ros.actions.Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=[
                '--x', '0', '--y', '0', '--z', '0',
                '--yaw', '0', '--pitch', '0', '--roll', '0',
                '--frame-id', 'odom', '--child-frame-id', 'base_link',
            ],
        ),
        launch_ros.actions.Node(
            package='buddy_safety',
            executable='command_arbiter',
            parameters=[
                {
                    'publish_rate_hz': 50.0,
                    'command_timeout_ms': 250.0,
                }
            ],
        ),
        launch_ros.actions.Node(
            package='buddy_safety',
            executable='safety_filter',
            parameters=[
                {
                    'publish_rate_hz': 50.0,
                    'startup_inhibit_ms': 0.0,
                    'require_scan': False,
                    'max_linear_acceleration': 100.0,
                    'max_angular_acceleration': 100.0,
                }
            ],
        ),
        launch_ros.actions.Node(
            package='buddy_world_model',
            executable='world_model_node',
            namespace='buddy',
            parameters=[
                {
                    'locations_file': PathJoinSubstitution(
                        [world_share, 'config', 'named_locations.yaml']
                    ),
                    'summary_rate_hz': 10.0,
                }
            ],
        ),
        launch_ros.actions.Node(
            package='buddy_bringup',
            executable='status_supervisor',
            parameters=[{'publish_rate_hz': 10.0}],
        ),
        launch_ros.actions.Node(
            package='buddy_bringup',
            executable='integration_fixture',
            parameters=[{'movement_seconds': 1.2}],
        ),
        launch_ros.actions.Node(
            package='buddy_navigation',
            executable='named_navigation_adapter',
            namespace='buddy',
            parameters=[
                PathJoinSubstitution(
                    [navigation_share, 'config', 'nav2.yaml']
                ),
                {
                    'dependency_timeout_sec': 3.0,
                    'navigation_timeout_sec': 10.0,
                },
            ],
        ),
        launch_ros.actions.Node(
            package='buddy_navigation',
            executable='velocity_boundary',
            namespace='buddy',
        ),
        launch_ros.actions.Node(
            package='buddy_capabilities',
            executable='capability_registry',
        ),
        launch_ros.actions.Node(
            package='buddy_task_executor',
            executable='task_executive',
        ),
        launch_ros.actions.Node(
            package='buddy_brain',
            executable='dialogue_node',
            parameters=[{'fake_model_response': MODEL_RESPONSE}],
        ),
    ]
    return launch.LaunchDescription(
        [
            launch.actions.SetEnvironmentVariable(
                'ROS_DOMAIN_ID', TEST_DOMAIN_ID
            ),
            launch.actions.SetEnvironmentVariable(
                'ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST'
            ),
            *nodes,
            launch_testing.actions.ReadyToTest(),
        ]
    )


class EndToEndSystemTest(unittest.TestCase):
    """Drive recognized utterances through real policy and motion layers."""

    @classmethod
    def setUpClass(cls):
        """Create one ROS test probe and spin it for all ordered assertions."""
        rclpy.init()
        cls.node = Node('buddy_end_to_end_probe')
        cls.executor = MultiThreadedExecutor(num_threads=2)
        cls.executor.add_node(cls.node)
        cls.thread = threading.Thread(target=cls.executor.spin, daemon=True)
        cls.thread.start()

        event_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        state_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        motion_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        cls.utterance = cls.node.create_publisher(
            RecognizedUtterance, '/buddy/voice/utterance', event_qos
        )
        cls.spoken = []
        cls.safe_commands = []
        cls.status = None
        cls.node.create_subscription(
            String,
            '/buddy/test/spoken',
            lambda message: cls.spoken.append(message.data),
            10,
        )
        cls.node.create_subscription(
            TwistStamped,
            '/buddy/motion/safe_cmd_vel',
            lambda message: cls.safe_commands.append(message.twist.linear.x),
            motion_qos,
        )
        cls.node.create_subscription(
            RobotStatus,
            '/buddy/status',
            cls._receive_status,
            state_qos,
        )
        cls.navigation = ActionClient(
            cls.node,
            NavigateToNamedLocation,
            '/buddy/navigation/navigate_to_named_location',
        )

    @classmethod
    def tearDownClass(cls):
        """Stop the probe but leave launch-testing processes to the runner."""
        cls.executor.shutdown()
        cls.thread.join(timeout=2.0)
        cls.node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    @classmethod
    def _receive_status(cls, message):
        cls.status = message

    @classmethod
    def _wait_for(cls, predicate, timeout=12.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        raise AssertionError('timed out waiting for integrated Buddy state')

    @classmethod
    def _publish_utterance(cls, text):
        message = RecognizedUtterance()
        message.header.stamp = cls.node.get_clock().now().to_msg()
        message.utterance_id.uuid = list(uuid.uuid4().bytes)
        message.text = text
        message.locale = 'en-US'
        message.confidence = 1.0
        message.is_final = True
        message.input_mode = RecognizedUtterance.INPUT_PUSH_TO_TALK
        cls.utterance.publish(message)

    def test_01_recognized_plan_executes_navigation_and_safe_motion(self):
        """Exercise confirmation, validation, motion, and spoken response."""
        self._wait_for(
            lambda: self.status is not None and self.status.motion_ready
        )
        self._wait_for(lambda: self.navigation.server_is_ready())
        time.sleep(2.5)
        self._publish_utterance('go home')
        self._wait_for(
            lambda: any('proceed' in text.casefold() for text in self.spoken)
        )
        self._publish_utterance('yes')
        self._wait_for(
            lambda: any(abs(value) > 0.05 for value in self.safe_commands)
        )
        self._wait_for(
            lambda: any(
                'task completed' in text.casefold()
                for text in self.spoken
            )
        )
        self._wait_for(
            lambda: self.safe_commands and abs(self.safe_commands[-1]) < 1.0e-9
        )

    def test_02_unknown_location_returns_structured_failure(self):
        """Unknown semantic destinations fail before a Nav2 side effect."""
        goal = NavigateToNamedLocation.Goal()
        goal.location_name = 'does-not-exist'
        handle_future = self.navigation.send_goal_async(goal)
        self._wait_for(handle_future.done)
        handle = handle_future.result()
        self.assertTrue(handle.accepted)
        result_future = handle.get_result_async()
        self._wait_for(result_future.done)
        result = result_future.result().result
        self.assertEqual(
            result.outcome,
            NavigateToNamedLocation.Result.OUTCOME_UNKNOWN_LOCATION,
        )

    def test_03_navigation_cancel_reaches_safe_stopped_state(self):
        """A navigation cancel stops Nav2 and leaves safe output at zero."""
        start_index = len(self.safe_commands)
        goal = NavigateToNamedLocation.Goal()
        goal.location_name = 'home'
        handle_future = self.navigation.send_goal_async(goal)
        self._wait_for(handle_future.done)
        handle = handle_future.result()
        self.assertTrue(handle.accepted)

        self._wait_for(
            lambda: any(
                abs(value) > 0.05
                for value in self.safe_commands[start_index:]
            )
        )
        cancel_future = handle.cancel_goal_async()
        self._wait_for(cancel_future.done)
        self.assertTrue(cancel_future.result().goals_canceling)

        result_future = handle.get_result_async()
        self._wait_for(result_future.done)
        wrapped_result = result_future.result()
        self.assertEqual(wrapped_result.status, GoalStatus.STATUS_CANCELED)
        self.assertEqual(
            wrapped_result.result.outcome,
            NavigateToNamedLocation.Result.OUTCOME_CANCELLED,
        )
        self._wait_for(
            lambda: self.safe_commands
            and abs(self.safe_commands[-1]) < 1.0e-9
        )
