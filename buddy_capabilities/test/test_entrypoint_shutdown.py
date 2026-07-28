"""Static teardown checks for the capability registry entry point."""

import inspect
import unittest

from buddy_capabilities.registry import main


class EntrypointShutdownTest(unittest.TestCase):
    """Keep shutdown behavior narrow and safe for launch signal handling."""

    def test_main_only_handles_shutdown_signals_and_checks_context(self):
        source = inspect.getsource(main)
        self.assertIn('except (KeyboardInterrupt, ExternalShutdownException):', source)
        self.assertIn('executor.shutdown()', source)
        self.assertIn('node.destroy_node()', source)
        self.assertIn('if rclpy.ok():', source)
