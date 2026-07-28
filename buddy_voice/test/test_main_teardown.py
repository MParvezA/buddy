"""Focused tests for quiet, idempotent ROS entry-point teardown."""

from buddy_voice import speak_node, voice_node
import pytest
from rclpy.executors import ExternalShutdownException


class _FakeNode:
    """Records whether an entry point destroyed its node."""

    def __init__(self, events: list[str] | None = None) -> None:
        self.destroyed = False
        self.cancelled = False
        self.events = events if events is not None else []

    def cancel_active_speech(self) -> None:
        """Match the Speak node's pre-shutdown cooperative cancellation hook."""
        self.cancelled = True
        self.events.append('cancel')

    def wait_for_active_speech(self) -> bool:
        """Match the Speak node's bounded action-drain hook."""
        self.events.append('drain')
        return True

    def shutdown_complete(self) -> bool:
        """Report that the fake has no active action work."""
        return True

    def shutdown_timeout_seconds(self) -> float:
        """Return a short deterministic fake shutdown bound."""
        return 0.1

    def get_logger(self) -> object:
        """Provide the teardown error logger contract without recording errors."""
        return type('Logger', (), {'error': lambda *_: None})()

    def destroy_node(self) -> None:
        """Record deterministic cleanup."""
        self.destroyed = True
        self.events.append('destroy')


class _FakeSpeakExecutor:
    """Minimal production-executor stand-in for entry-point teardown tests."""

    def __init__(self, exception: BaseException, events: list[str] | None = None) -> None:
        self.exception = exception
        self.nodes: list[object] = []
        self.shutdown_called = False
        self.events = events if events is not None else []

    def add_node(self, node: object) -> None:
        """Record the action node added by the production entry point."""
        self.nodes.append(node)

    def remove_node(self, node: object) -> None:
        """Record action-node detachment before worker shutdown."""
        self.nodes.remove(node)
        self.events.append('remove')

    def spin(self) -> None:
        """Reproduce executor termination without constructing ROS resources."""
        raise self.exception

    def spin_once(self, timeout_sec: float) -> None:
        """Record a bounded cleanup spin when active work requires it."""
        self.events.append(f'spin_once:{timeout_sec}')

    def drain_submitted_callbacks(self, timeout_sec: float) -> tuple[()]:
        """Record terminal callback outcome collection."""
        self.events.append('drain_callbacks')
        return ()

    def shutdown_workers(self, timeout_sec: float) -> bool:
        """Record closure of the private executor worker pool."""
        self.events.append('shutdown_workers')
        return True

    def shutdown(self, timeout_sec: float = 0.0) -> None:
        """Record deterministic executor teardown."""
        self.shutdown_called = True
        self.events.append('shutdown')


@pytest.mark.parametrize(
    ('module', 'node_class_name'),
    ((voice_node, 'BuddyVoiceNode'), (speak_node, 'BuddySpeakNode')),
)
@pytest.mark.parametrize(
    'shutdown_exception',
    (KeyboardInterrupt(), ExternalShutdownException()),
)
def test_main_quietly_handles_shutdown_exceptions(
        monkeypatch: pytest.MonkeyPatch,
        module: object,
        node_class_name: str,
        shutdown_exception: BaseException) -> None:
    """Shutdown exceptions are quiet and never cause a second shutdown call."""
    events: list[str] = []
    node = _FakeNode(events)
    shutdown_calls: list[bool] = []
    monkeypatch.setattr(module, node_class_name, lambda: node)
    monkeypatch.setattr(module.rclpy, 'init', lambda args=None, **_: None)
    monkeypatch.setattr(module.rclpy, 'ok', lambda: False)
    monkeypatch.setattr(module.rclpy, 'shutdown', lambda: shutdown_calls.append(True))

    executor = None
    if module is speak_node:
        executor = _FakeSpeakExecutor(shutdown_exception, events)
        monkeypatch.setattr(module, 'create_speak_executor', lambda: executor)
    else:
        def raise_shutdown(_: object) -> None:
            raise shutdown_exception

        monkeypatch.setattr(module.rclpy, 'spin', raise_shutdown)

    module.main()

    assert node.destroyed
    assert shutdown_calls == []
    if executor is not None:
        assert executor.nodes == []
        assert executor.shutdown_called
        assert node.cancelled
        assert events == [
            'cancel', 'drain_callbacks', 'shutdown_workers', 'remove', 'shutdown', 'destroy']


@pytest.mark.parametrize(
    ('module', 'node_class_name'),
    ((voice_node, 'BuddyVoiceNode'), (speak_node, 'BuddySpeakNode')),
)
def test_main_does_not_mask_runtime_exceptions(
        monkeypatch: pytest.MonkeyPatch,
        module: object,
        node_class_name: str) -> None:
    """Unexpected failures propagate after node and active-context cleanup."""
    events: list[str] = []
    node = _FakeNode(events)
    shutdown_calls: list[bool] = []
    monkeypatch.setattr(module, node_class_name, lambda: node)
    monkeypatch.setattr(module.rclpy, 'init', lambda args=None, **_: None)
    monkeypatch.setattr(module.rclpy, 'ok', lambda: True)
    monkeypatch.setattr(module.rclpy, 'shutdown', lambda: shutdown_calls.append(True))

    executor = None
    if module is speak_node:
        executor = _FakeSpeakExecutor(RuntimeError('unexpected spin failure'), events)
        monkeypatch.setattr(module, 'create_speak_executor', lambda: executor)
    else:
        def raise_runtime(_: object) -> None:
            raise RuntimeError('unexpected spin failure')

        monkeypatch.setattr(module.rclpy, 'spin', raise_runtime)

    with pytest.raises(RuntimeError, match='unexpected spin failure'):
        module.main()

    assert node.destroyed
    assert shutdown_calls == [True]
    if executor is not None:
        assert executor.nodes == []
        assert executor.shutdown_called
        assert node.cancelled
        assert events == [
            'cancel', 'drain_callbacks', 'shutdown_workers', 'remove', 'shutdown', 'destroy']


def test_speak_shutdown_detaches_before_destroying_action_handles() -> None:
    """The SIGINT teardown order cannot leave a destroyed server in a wait set."""
    events: list[str] = []
    node = _FakeNode(events)
    executor = _FakeSpeakExecutor(KeyboardInterrupt(), events)
    executor.add_node(node)

    speak_node._shutdown_speak_node(node, executor)

    assert events == [
        'cancel', 'drain_callbacks', 'shutdown_workers', 'remove', 'shutdown', 'destroy']
    assert node.destroyed
    assert executor.shutdown_called
