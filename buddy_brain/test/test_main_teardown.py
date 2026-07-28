# Copyright 2026 SyncRobot

"""Focused entrypoint teardown tests without starting a ROS participant."""

from unittest.mock import Mock, patch

from rclpy.executors import ExternalShutdownException

from buddy_brain import dialogue_node


def _run_main(spin_exception, context_ok):
    events = []
    node = Mock()
    node.destroy_node.side_effect = lambda: events.append("destroy")
    with (
        patch.object(dialogue_node.rclpy, "init") as initialize,
        patch.object(dialogue_node, "DialogueNode", return_value=node),
        patch.object(dialogue_node.rclpy, "spin", side_effect=spin_exception),
        patch.object(dialogue_node.rclpy, "ok", return_value=context_ok),
        patch.object(
            dialogue_node.rclpy,
            "shutdown",
            side_effect=lambda: events.append("shutdown"),
        ) as shutdown,
    ):
        dialogue_node.main(args=["--ros-args"])
    initialize.assert_called_once_with(args=["--ros-args"])
    return events, shutdown


def test_keyboard_interrupt_destroys_node_then_shuts_down_live_context():
    events, shutdown = _run_main(KeyboardInterrupt(), True)
    assert events == ["destroy", "shutdown"]
    shutdown.assert_called_once_with()


def test_external_shutdown_does_not_request_a_second_shutdown():
    events, shutdown = _run_main(ExternalShutdownException(), False)
    assert events == ["destroy"]
    shutdown.assert_not_called()


def test_ordinary_runtime_exception_is_not_swallowed():
    try:
        _run_main(RuntimeError("spin failed"), True)
    except RuntimeError as exc:
        assert str(exc) == "spin failed"
    else:
        raise AssertionError("ordinary runtime exception was swallowed")


def test_entrypoint_static_shape_has_narrow_shutdown_handling():
    source = dialogue_node.main.__code__
    assert "ExternalShutdownException" in source.co_names
    assert "KeyboardInterrupt" in source.co_names
    assert "ok" in source.co_names
