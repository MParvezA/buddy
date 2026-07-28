"""Regression coverage for bounded Speak executor shutdown on ROS 2 Jazzy."""

from collections import deque
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from buddy_voice import speak_node
from buddy_voice.speak_node import BuddySpeakNode, DrainingSpeakExecutor
import pytest
import rclpy
from rclpy.signals import SignalHandlerOptions


def _bare_executor(*, futures: list[object], pending: dict[object, object] | None = None,
                   ready: deque[object] | None = None) -> DrainingSpeakExecutor:
    """Create a private-task-registry fixture without allocating ROS workers."""
    executor = object.__new__(DrainingSpeakExecutor)
    executor._futures = futures
    executor._sigint_gc = None
    executor._tasks_lock = threading.Lock()
    executor._pending_tasks = pending or {}
    executor._ready_tasks = ready or deque()
    return executor


def test_callback_drain_retrieves_completed_result_and_releases_registries() -> None:
    """Completed callback outcomes are read before their Jazzy references vanish."""
    task = Mock()
    task.cancelled.return_value = False
    task.done.return_value = True
    task.exception.return_value = None
    executor = _bare_executor(
        futures=[task], pending={task: SimpleNamespace(source_entity=Mock())}, ready=deque([task]))

    assert executor.drain_submitted_callbacks(0.1) == ()
    task.exception.assert_called_once_with()
    task.result.assert_called_once_with()
    assert executor._futures == []
    assert executor._pending_tasks == {}
    assert executor._ready_tasks == deque()


def test_callback_drain_keeps_cancel_race_until_terminal_result_is_retrieved() -> None:
    """A task that begins executing during cancel is never silently discarded."""
    class RacingTask:
        """Transitions from queued to done when cancellation loses its race."""

        def __init__(self) -> None:
            self.cancel_calls = 0
            self.result_calls = 0
            self.running = False

        def cancelled(self) -> bool:
            return False

        def done(self) -> bool:
            return self.running

        def executing(self) -> bool:
            return self.running

        def cancel(self) -> None:
            self.cancel_calls += 1
            self.running = True

        def exception(self) -> None:
            return None

        def result(self) -> None:
            self.result_calls += 1

    task = RacingTask()
    executor = _bare_executor(
        futures=[task], pending={task: SimpleNamespace(source_entity=Mock())})

    executor.drain_submitted_callbacks(0.1)

    assert task.cancel_calls == 1
    assert task.result_calls == 1
    assert executor._futures == []
    assert executor._pending_tasks == {}


def test_callback_drain_retrieves_error_before_continuing_cleanup() -> None:
    """A completed callback exception is surfaced after its registry is released."""
    task = Mock()
    task.cancelled.return_value = False
    task.done.return_value = True
    task.exception.return_value = RuntimeError('callback failed')
    executor = _bare_executor(futures=[task])

    with pytest.raises(RuntimeError, match='callback failed'):
        executor.drain_submitted_callbacks(0.1)

    task.exception.assert_called_once_with()
    task.result.assert_not_called()
    assert executor._futures == []


def test_worker_pool_is_closed_and_non_daemon_workers_are_reaped() -> None:
    """Stock Jazzy's private ThreadPoolExecutor is closed within a finite bound."""
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    executor = DrainingSpeakExecutor(num_threads=2)
    completed = threading.Event()
    try:
        future = executor._executor.submit(completed.set)
        assert completed.wait(0.5)
        future.result(timeout=0.5)
        assert executor.shutdown_workers(0.4)
        assert all(not worker.is_alive() for worker in executor._executor._threads)
        executor.shutdown(timeout_sec=0.0)
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_shutdown_continues_after_callback_drain_failure() -> None:
    """A retrieved callback failure cannot skip worker, waitable, or node cleanup."""
    events: list[str] = []
    logger = Mock()
    node = Mock()
    node.shutdown_complete.return_value = True
    node.shutdown_timeout_seconds.return_value = 0.1
    node.get_logger.return_value = logger
    node.cancel_active_speech.side_effect = lambda: events.append('cancel')
    node.destroy_node.side_effect = lambda: events.append('destroy')
    executor = Mock()
    executor.drain_submitted_callbacks.side_effect = RuntimeError('drain failed')
    executor.shutdown_workers.side_effect = lambda _: events.append('workers') or True
    executor.remove_node.side_effect = lambda _: events.append('remove')
    executor.shutdown.side_effect = lambda **_: events.append('shutdown')

    speak_node._shutdown_speak_node(node, executor)

    assert events == ['cancel', 'workers', 'remove', 'shutdown', 'destroy']
    logger.error.assert_called_once()
    assert 'drain failed' in logger.error.call_args.args[0]


def test_destroy_node_releases_its_action_waitable_idempotently() -> None:
    """Speak server destruction leaves no ActionServer waitable retained by its node."""
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = BuddySpeakNode()
    action_server = node._action_server
    try:
        assert action_server in node.waitables
        node.destroy_node()
        node.destroy_node()
        assert action_server not in node.waitables
    finally:
        if action_server in node.waitables:
            action_server.destroy()
        if rclpy.ok():
            rclpy.shutdown()
