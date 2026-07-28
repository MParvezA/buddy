"""Static teardown checks for the task executive entry point."""

import inspect
import os
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from buddy_task_executor import executive
import rclpy
from rclpy.signals import SignalHandlerOptions


class EntrypointShutdownTest(unittest.TestCase):
    """Keep shutdown behavior narrow and safe for launch signal handling."""

    def test_executor_drain_retrieves_completed_future_outcome(self):
        executor = object.__new__(executive.DrainingMultiThreadedExecutor)
        future = Mock()
        future.cancelled.return_value = False
        future.done.return_value = True
        future.exception.return_value = None
        future.result.return_value = 'completed'
        executor._futures = [future]
        executor._sigint_gc = None

        self.assertEqual(executor.drain_submitted_callbacks(0.0), ())
        future.exception.assert_called_once_with()
        future.result.assert_called_once_with()
        self.assertEqual(executor._futures, [])

    def test_executor_drain_raises_completed_future_exception(self):
        executor = object.__new__(executive.DrainingMultiThreadedExecutor)
        future = Mock()
        error = RuntimeError('callback failed')
        future.cancelled.return_value = False
        future.done.return_value = True
        future.exception.return_value = error
        executor._futures = [future]
        executor._sigint_gc = None

        with self.assertRaisesRegex(RuntimeError, 'callback failed'):
            executor.drain_submitted_callbacks(0.0)

        future.exception.assert_called_once_with()
        future.result.assert_not_called()
        self.assertEqual(executor._futures, [])

    def test_executor_drain_cancels_queued_future(self):
        executor = object.__new__(executive.DrainingMultiThreadedExecutor)
        future = Mock()
        future.cancelled.side_effect = [False, True]
        future.done.return_value = False
        future.executing.return_value = False
        future.cancel.return_value = True
        source = SimpleNamespace(topic='/buddy/tasks/execute')
        executor._futures = [future]
        executor._sigint_gc = None
        executor._tasks_lock = threading.Lock()
        executor._pending_tasks = {
            future: SimpleNamespace(source_entity=source),
        }

        cancelled = executor.drain_submitted_callbacks(0.0)

        self.assertEqual(len(cancelled), 1)
        self.assertIn('/buddy/tasks/execute', cancelled[0])
        future.cancel.assert_called_once_with()
        self.assertEqual(executor._futures, [])

    def test_executor_drain_keeps_racing_future_until_its_outcome_is_retrieved(self):
        executor = object.__new__(executive.DrainingMultiThreadedExecutor)
        future = Mock()
        future.cancelled.side_effect = [False, False, False]
        future.done.side_effect = [False, True]
        future.executing.return_value = False
        future.cancel.return_value = False
        future.exception.return_value = None
        future.result.return_value = 'completed after cancellation race'
        source = SimpleNamespace(topic='/buddy/tasks/execute')
        executor._futures = [future]
        executor._sigint_gc = None
        executor._tasks_lock = threading.Lock()
        executor._pending_tasks = {
            future: SimpleNamespace(source_entity=source),
        }

        executor.drain_submitted_callbacks(0.1)

        future.cancel.assert_called_once_with()
        future.exception.assert_called_once_with()
        future.result.assert_called_once_with()
        self.assertEqual(executor._futures, [])

    def test_executor_shutdown_releases_idle_workers_within_bound(self):
        os.environ.setdefault('ROS_LOG_DIR', '/tmp')
        os.environ.setdefault('FASTDDS_BUILTIN_TRANSPORTS', 'SHM')
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
        executor = executive.DrainingMultiThreadedExecutor(num_threads=1)
        ran = threading.Event()
        try:
            completed = executor._executor.submit(ran.set)
            self.assertTrue(ran.wait(0.5))
            completed.result(timeout=0.5)
            started = time.monotonic()
            self.assertTrue(executor.shutdown(timeout_sec=0.4))
            self.assertLess(time.monotonic() - started, 0.5)
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_executor_drain_times_out_for_executing_future(self):
        executor = object.__new__(executive.DrainingMultiThreadedExecutor)
        future = Mock()
        future.cancelled.return_value = False
        future.done.return_value = False
        future.executing.return_value = True
        source = SimpleNamespace(topic='/buddy/tasks/execute')
        executor._futures = [future]
        executor._sigint_gc = None
        executor._tasks_lock = threading.Lock()
        executor._pending_tasks = {
            future: SimpleNamespace(source_entity=source),
        }

        with self.assertRaisesRegex(
                TimeoutError, 'executor callbacks did not finish before shutdown'):
            executor.drain_submitted_callbacks(0.0)

        future.cancel.assert_not_called()
        self.assertEqual(executor._futures, [future])

    def test_main_only_handles_shutdown_signals_and_checks_context(self):
        source = inspect.getsource(executive.main)
        self.assertIn('except (KeyboardInterrupt, ExternalShutdownException):', source)
        self.assertIn('executor.shutdown(timeout_sec=0.25)', source)
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
        executor.drain_submitted_callbacks.side_effect = (
            lambda timeout_sec: events.append('drain_callbacks') or ())
        executor.shutdown.side_effect = (
            lambda **_kwargs: events.append('executor_shutdown'))
        with (
                patch.object(executive.rclpy, 'init') as initialize,
                patch.object(executive.rclpy, 'ok', return_value=True),
                patch.object(executive.rclpy, 'shutdown',
                             side_effect=lambda: events.append('rclpy_shutdown')),
                patch.object(executive, 'TaskExecutive', return_value=node),
                patch.object(
                    executive, 'DrainingMultiThreadedExecutor', return_value=executor)):
            executive.main(args=['--ros-args'])

        initialize.assert_called_once_with(
            args=['--ros-args'], signal_handler_options=SignalHandlerOptions.NO)
        node.request_shutdown.assert_called_once_with()
        self.assertEqual(
            events,
            ['request_shutdown', 'spin_once', 'drain_callbacks', 'executor_shutdown',
             'destroy_node', 'rclpy_shutdown'])

    def test_destroy_node_explicitly_removes_owned_action_waitables(self):
        os.environ.setdefault('ROS_LOG_DIR', '/tmp')
        os.environ.setdefault('FASTDDS_BUILTIN_TRANSPORTS', 'SHM')
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
        node = executive.TaskExecutive()
        owned_actions = (node._server, node._speak_client, node._navigate_client)
        destroy_calls = [
            patch.object(action, 'destroy', wraps=action.destroy)
            for action in owned_actions
        ]
        try:
            with destroy_calls[0] as server_destroy:
                with destroy_calls[1] as speak_destroy:
                    with destroy_calls[2] as navigate_destroy:
                        self.assertTrue(
                            all(action in node.waitables for action in owned_actions))
                        node.destroy_node()
                        node.destroy_node()
                        self.assertTrue(
                            all(action not in node.waitables for action in owned_actions))
                        for destroy in (server_destroy, speak_destroy, navigate_destroy):
                            destroy.assert_called_once_with()
        finally:
            for action in owned_actions:
                if action in node.waitables:
                    action.destroy()
            if rclpy.ok():
                rclpy.shutdown()
