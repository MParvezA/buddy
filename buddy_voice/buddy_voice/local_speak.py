"""Explicit local Piper Speak server; simulation continues to use its fake server."""

from __future__ import annotations

import argparse

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.signals import SignalHandlerOptions

from .local_providers import PiperTextToSpeechProvider, PiperVoice
from .speak_node import _shutdown_speak_node, BuddySpeakNode, create_speak_executor


def _arguments() -> argparse.ArgumentParser:
    """Require both configured local voices rather than guessing/download them."""
    parser = argparse.ArgumentParser(description='Buddy local Piper Speak server')
    parser.add_argument('--piper-binary', required=True)
    parser.add_argument('--playback-binary', default='pw-play')
    parser.add_argument('--sink', default=None, help='PipeWire sink; default sink when omitted')
    parser.add_argument('--en-model', required=True)
    parser.add_argument('--en-config', required=True)
    parser.add_argument('--en-voice', default='en_default')
    parser.add_argument('--de-model', required=True)
    parser.add_argument('--de-config', required=True)
    parser.add_argument('--de-voice', default='de_default')
    parser.add_argument('--synthesis-timeout-seconds', type=int, default=15)
    parser.add_argument('--playback-timeout-seconds', type=int, default=30)
    return parser


def _parse_arguments(argv: list[str] | None) -> tuple[argparse.Namespace, list[str]]:
    """Parse local Piper options while retaining ordinary ROS 2 arguments/remaps."""
    return _arguments().parse_known_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run a real local output server only when its assets are explicitly supplied."""
    args, ros_args = _parse_arguments(argv)
    provider = PiperTextToSpeechProvider(
        piper_binary=args.piper_binary,
        playback_binary=args.playback_binary,
        sink=args.sink,
        english_voice=PiperVoice(args.en_voice, 'en-US', args.en_model, args.en_config),
        german_voice=PiperVoice(args.de_voice, 'de-DE', args.de_model, args.de_config),
        synthesis_timeout_seconds=args.synthesis_timeout_seconds,
        playback_timeout_seconds=args.playback_timeout_seconds,
    )
    rclpy.init(args=ros_args, signal_handler_options=SignalHandlerOptions.NO)
    node = None
    executor = None
    try:
        node = BuddySpeakNode(
            provider,
            synthesis_timeout_seconds=args.synthesis_timeout_seconds,
            playback_timeout_seconds=args.playback_timeout_seconds,
            node_name='local_speak_server',
        )
        executor = create_speak_executor()
        executor.add_node(node)
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        _shutdown_speak_node(node, executor)
        if rclpy.ok():
            rclpy.shutdown()
