"""Static teardown checks for the task executive entry point."""

import inspect
import unittest
from unittest.mock import Mock, patch

from buddy_task_executor import executive
from rclpy.signals import SignalHandlerOptions


class EntrypointShutdownTest(unittest.TestCase):
    """Keep shutdown behavior narrow and safe for launch signal handling."""

    def test_main_only_handles_shutdown_signals_and_checks_context(self):
        source = inspect.getsource(executive.main)
        self.assertIn('except (KeyboardInterrupt, ExternalShutdownException):', source)
        self.assertIn('executor.shutdown()', source)
        self.assertIn('node.destroy_node()', source)
        self.assertIn('if rclpy.ok():', source)

    def test_sigint_requests_and_drains_active_task_before_destroying_node(self):
        events = []
        node = Mock()
        node.shutdown_complete.side_effect = [False, True]
        node.shutdown_timeout_seconds.return_value = 0.5
        node.request_shutdown.side_effect = lambda: events.append('request_shutdown')
        node.destroy_node.side_effect = lambda: events.append('destroy_node')
        executor = Mock()
        executor.spin.side_effect = KeyboardInterrupt()
        executor.spin_once.side_effect = lambda timeout_sec: events.append('spin_once')
        executor.shutdown.side_effect = lambda: events.append('executor_shutdown')
        with (
                patch.object(executive.rclpy, 'init') as initialize,
                patch.object(executive.rclpy, 'ok', return_value=True),
                patch.object(executive.rclpy, 'shutdown',
                             side_effect=lambda: events.append('rclpy_shutdown')),
                patch.object(executive, 'TaskExecutive', return_value=node),
                patch.object(executive, 'MultiThreadedExecutor', return_value=executor)):
            executive.main(args=['--ros-args'])

        initialize.assert_called_once_with(
            args=['--ros-args'], signal_handler_options=SignalHandlerOptions.NO)
        node.request_shutdown.assert_called_once_with()
        self.assertEqual(
            events,
            ['request_shutdown', 'spin_once', 'executor_shutdown',
             'destroy_node', 'rclpy_shutdown'])
