"""Deterministic steady-time tests for the Gazebo command-adapter heartbeat."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

from builtin_interfaces.msg import Time
from diagnostic_msgs.msg import DiagnosticStatus


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / 'buddy_gazebo' / 'safe_cmd_vel_adapter.py')
SPEC = importlib.util.spec_from_file_location('safe_cmd_vel_adapter', MODULE_PATH)
ADAPTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = ADAPTER
SPEC.loader.exec_module(ADAPTER)


class TestAdapterHealth(unittest.TestCase):
    def test_rejects_non_finite_or_non_positive_timing_parameters(self):
        for invalid in (0, -0.1, float('inf'), float('nan'), 'not-a-duration'):
            with self.assertRaises(ValueError):
                ADAPTER.positive_finite_seconds(invalid, 'test_parameter')
        self.assertEqual(ADAPTER.positive_finite_seconds('0.2', 'test_parameter'), 0.2)

    def test_startup_waiting_then_fresh_then_stale_uses_steady_time(self):
        health = ADAPTER.AdapterHealth.create(0.25)
        level, _, state, age_ms, publisher = health.snapshot(100)
        self.assertEqual((level, state, age_ms, publisher),
                         (DiagnosticStatus.WARN, 'waiting', 'unknown', 'ready'))

        health = health.command_received(1_000_000_000).publish_succeeded()
        level, _, state, age_ms, publisher = health.snapshot(1_100_000_000)
        self.assertEqual((level, state, age_ms, publisher),
                         (DiagnosticStatus.OK, 'fresh', '100.0', 'ready'))

        level, message, state, age_ms, publisher = health.snapshot(1_250_000_001)
        self.assertEqual(level, DiagnosticStatus.WARN)
        self.assertIn('stale', message)
        self.assertEqual((state, age_ms, publisher), ('stale', '250.0', 'ready'))

    def test_publication_exception_is_error_until_a_fresh_success(self):
        health = ADAPTER.AdapterHealth.create(0.25).command_received(10)
        health = health.publish_failed(RuntimeError('transport disconnected'))
        level, message, state, _, publisher = health.snapshot(11)
        self.assertEqual(level, DiagnosticStatus.ERROR)
        self.assertIn('transport disconnected', message)
        self.assertEqual((state, publisher), ('fresh', 'error'))

        health = health.command_received(20).publish_succeeded()
        level, _, state, _, publisher = health.snapshot(21)
        self.assertEqual((level, state, publisher),
                         (DiagnosticStatus.OK, 'fresh', 'ready'))

    def test_heartbeat_publishes_the_stable_controller_name_and_steady_age(self):
        published = []
        fake_node = SimpleNamespace(
            _health=ADAPTER.AdapterHealth.create(0.25).command_received(1_000_000_000)
            .publish_succeeded(),
            _steady_time_ns=lambda: 1_100_000_000,
            _diagnostics=SimpleNamespace(publish=published.append),
            get_clock=lambda: SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: Time())),
        )

        ADAPTER.SafeCommandAdapter._publish_diagnostics(fake_node)

        self.assertEqual(len(published), 1)
        status = published[0].status[0]
        values = {item.key: item.value for item in status.values}
        self.assertEqual(status.name, 'buddy_base_controller')
        self.assertEqual(status.level, DiagnosticStatus.OK)
        self.assertEqual(values['safe_command_receipt'], 'fresh')
        self.assertEqual(values['safe_command_receipt_age_ms'], '100.0')


if __name__ == '__main__':
    unittest.main()
