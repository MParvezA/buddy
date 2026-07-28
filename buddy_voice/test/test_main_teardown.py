"""Focused tests for quiet, idempotent ROS entry-point teardown."""

from buddy_voice import speak_node, voice_node
import pytest
from rclpy.executors import ExternalShutdownException


class _FakeNode:
    """Records whether an entry point destroyed its node."""

    def __init__(self) -> None:
        self.destroyed = False
        self.cancelled = False

    def cancel_active_speech(self) -> None:
        """Match the Speak node's pre-shutdown cooperative cancellation hook."""
        self.cancelled = True

    def wait_for_active_speech(self) -> bool:
        """Match the Speak node's bounded action-drain hook."""
        return True

    def destroy_node(self) -> None:
        """Record deterministic cleanup."""
        self.destroyed = True


class _FakeSpeakExecutor:
    """Minimal production-executor stand-in for entry-point teardown tests."""

    def __init__(self, exception: BaseException) -> None:
        self.exception = exception
        self.nodes: list[object] = []
        self.shutdown_called = False

    def add_node(self, node: object) -> None:
        """Record the action node added by the production entry point."""
        self.nodes.append(node)

    def spin(self) -> None:
        """Reproduce executor termination without constructing ROS resources."""
        raise self.exception

    def shutdown(self) -> None:
        """Record deterministic executor teardown."""
        self.shutdown_called = True


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
    node = _FakeNode()
    shutdown_calls: list[bool] = []
    monkeypatch.setattr(module, node_class_name, lambda: node)
    monkeypatch.setattr(module.rclpy, 'init', lambda args=None: None)
    monkeypatch.setattr(module.rclpy, 'ok', lambda: False)
    monkeypatch.setattr(module.rclpy, 'shutdown', lambda: shutdown_calls.append(True))

    executor = None
    if module is speak_node:
        executor = _FakeSpeakExecutor(shutdown_exception)
        monkeypatch.setattr(module, 'create_speak_executor', lambda: executor)
    else:
        def raise_shutdown(_: object) -> None:
            raise shutdown_exception

        monkeypatch.setattr(module.rclpy, 'spin', raise_shutdown)

    module.main()

    assert node.destroyed
    assert shutdown_calls == []
    if executor is not None:
        assert executor.nodes == [node]
        assert executor.shutdown_called
        assert node.cancelled


@pytest.mark.parametrize(
    ('module', 'node_class_name'),
    ((voice_node, 'BuddyVoiceNode'), (speak_node, 'BuddySpeakNode')),
)
def test_main_does_not_mask_runtime_exceptions(
        monkeypatch: pytest.MonkeyPatch,
        module: object,
        node_class_name: str) -> None:
    """Unexpected failures propagate after node and active-context cleanup."""
    node = _FakeNode()
    shutdown_calls: list[bool] = []
    monkeypatch.setattr(module, node_class_name, lambda: node)
    monkeypatch.setattr(module.rclpy, 'init', lambda args=None: None)
    monkeypatch.setattr(module.rclpy, 'ok', lambda: True)
    monkeypatch.setattr(module.rclpy, 'shutdown', lambda: shutdown_calls.append(True))

    executor = None
    if module is speak_node:
        executor = _FakeSpeakExecutor(RuntimeError('unexpected spin failure'))
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
        assert executor.nodes == [node]
        assert executor.shutdown_called
        assert node.cancelled
