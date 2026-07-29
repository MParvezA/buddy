"""Focused argument forwarding tests for the explicit local provider entry points."""

from __future__ import annotations

import builtins

from buddy_voice import local_speak, terminal_ptt


ROS_ARGUMENTS = ['--ros-args', '-r', '__node:=operator_voice', '--log-level', 'debug']


def test_terminal_parser_preserves_ros_arguments() -> None:
    """Terminal PTT keeps remaps and logging arguments for rclpy."""
    provider_args, ros_args = terminal_ptt._parse_arguments([
        '--whisper-binary', '/opt/whisper-cli', '--whisper-model', '/opt/base.bin',
        '--stt-threads', '2', *ROS_ARGUMENTS,
    ])
    assert provider_args.whisper_binary == '/opt/whisper-cli'
    assert provider_args.stt_threads == 2
    assert ros_args == ROS_ARGUMENTS


def test_local_speak_parser_preserves_ros_arguments() -> None:
    """Local Piper output keeps remaps and logging arguments for rclpy."""
    provider_args, ros_args = local_speak._parse_arguments([
        '--piper-binary', '/opt/piper', '--en-model', '/opt/en.onnx',
        '--en-config', '/opt/en.json', '--de-model', '/opt/de.onnx',
        '--de-config', '/opt/de.json', *ROS_ARGUMENTS,
    ])
    assert provider_args.piper_binary == '/opt/piper'
    assert provider_args.en_voice == 'en_default'
    assert ros_args == ROS_ARGUMENTS


def test_terminal_main_passes_ros_arguments_to_rclpy(
        monkeypatch) -> None:
    """Terminal PTT hands remaining ROS arguments to the client-library init."""
    init_calls = []
    events = []

    class Audio:
        """Minimal capture provider substitute for entry-point testing."""

        def close(self):
            events.append('close')

    class Node:
        """Minimal voice node substitute for entry-point testing."""

        def destroy_node(self):
            events.append('destroy')

    monkeypatch.setattr(terminal_ptt, 'PipeWirePushToTalkAudioInput', lambda **_: Audio())
    monkeypatch.setattr(terminal_ptt, 'WhisperCppSpeechToTextProvider', lambda **_: object())
    monkeypatch.setattr(terminal_ptt, 'BuddyVoiceNode', lambda *_args, **_kwargs: Node())
    monkeypatch.setattr(terminal_ptt.rclpy, 'init', lambda *, args: init_calls.append(args))
    monkeypatch.setattr(terminal_ptt.rclpy, 'ok', lambda: False)
    monkeypatch.setattr(terminal_ptt.rclpy, 'shutdown', lambda: events.append('shutdown'))
    monkeypatch.setattr(builtins, 'input', lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))

    terminal_ptt.main([
        '--whisper-binary', '/opt/whisper-cli', '--whisper-model', '/opt/base.bin', *ROS_ARGUMENTS])

    assert init_calls == [ROS_ARGUMENTS]
    assert events == ['close', 'destroy']


def test_local_speak_main_passes_ros_arguments_to_rclpy(
        monkeypatch) -> None:
    """Local Piper output hands remaining ROS arguments to client-library init."""
    init_calls = []
    shutdown_calls = []

    class Executor:
        """Minimal executor that exits through the normal keyboard path."""

        def add_node(self, node):
            pass

        def spin(self):
            raise KeyboardInterrupt()

    monkeypatch.setattr(local_speak, 'PiperTextToSpeechProvider', lambda **_: object())
    monkeypatch.setattr(local_speak, 'BuddySpeakNode', lambda *_args, **_kwargs: object())
    monkeypatch.setattr(local_speak, 'create_speak_executor', lambda: Executor())
    monkeypatch.setattr(
        local_speak, '_shutdown_speak_node',
        lambda node, executor: shutdown_calls.append((node, executor)))
    monkeypatch.setattr(
        local_speak.rclpy, 'init',
        lambda *, args, signal_handler_options: init_calls.append((args, signal_handler_options)))
    monkeypatch.setattr(local_speak.rclpy, 'ok', lambda: False)

    local_speak.main([
        '--piper-binary', '/opt/piper', '--en-model', '/opt/en.onnx',
        '--en-config', '/opt/en.json', '--de-model', '/opt/de.onnx',
        '--de-config', '/opt/de.json', *ROS_ARGUMENTS])

    assert init_calls[0][0] == ROS_ARGUMENTS
    assert shutdown_calls
