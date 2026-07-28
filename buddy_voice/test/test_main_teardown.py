"""Focused tests for quiet, idempotent ROS entry-point teardown."""

from buddy_voice import speak_node, voice_node
import pytest
from rclpy.executors import ExternalShutdownException


class _FakeNode:
    """Records whether an entry point destroyed its node."""

    def __init__(self) -> None:
        self.destroyed = False

    def destroy_node(self) -> None:
        """Record deterministic cleanup."""
        self.destroyed = True


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

    def raise_shutdown(_: object) -> None:
        raise shutdown_exception

    monkeypatch.setattr(module.rclpy, 'spin', raise_shutdown)

    module.main()

    assert node.destroyed
    assert shutdown_calls == []


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

    def raise_runtime(_: object) -> None:
        raise RuntimeError('unexpected spin failure')

    monkeypatch.setattr(module.rclpy, 'spin', raise_runtime)

    with pytest.raises(RuntimeError, match='unexpected spin failure'):
        module.main()

    assert node.destroyed
    assert shutdown_calls == [True]
