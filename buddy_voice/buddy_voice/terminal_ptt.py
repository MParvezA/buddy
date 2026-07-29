"""Interactive terminal-only local push-to-talk entry point for development."""

from __future__ import annotations

import argparse
from threading import Event, Thread

import rclpy

from .local_providers import PipeWirePushToTalkAudioInput, WhisperCppSpeechToTextProvider
from .voice_node import BuddyVoiceNode


def _arguments() -> argparse.ArgumentParser:
    """Build explicit local-only runtime configuration without changing launch defaults."""
    parser = argparse.ArgumentParser(description='Buddy local PipeWire push-to-talk')
    parser.add_argument('--record-binary', default='pw-record')
    parser.add_argument('--device', default=None, help='PipeWire source name; default source when omitted')
    parser.add_argument('--maximum-capture-seconds', type=int, default=15)
    parser.add_argument('--whisper-binary', required=True)
    parser.add_argument('--whisper-model', required=True)
    parser.add_argument('--stt-threads', type=int, default=2)
    parser.add_argument('--stt-timeout-seconds', type=int, default=30)
    parser.add_argument('--stt-language', choices=('auto', 'en', 'de'), default='auto')
    parser.add_argument('--locale', choices=('en-US', 'de-DE'), default='en-US')
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run Enter-to-start/Enter-to-stop capture beside the fake simulation launch."""
    args = _arguments().parse_args(argv)
    audio = PipeWirePushToTalkAudioInput(
        record_binary=args.record_binary,
        device=args.device,
        maximum_capture_seconds=args.maximum_capture_seconds,
        locale=args.locale,
    )
    stt = WhisperCppSpeechToTextProvider(
        binary=args.whisper_binary,
        model=args.whisper_model,
        threads=args.stt_threads,
        timeout_seconds=args.stt_timeout_seconds,
        language=args.stt_language,
    )
    rclpy.init()
    node = BuddyVoiceNode(audio, stt, node_name='terminal_ptt')
    released: Event | None = None
    worker: Thread | None = None
    try:
        while rclpy.ok():
            input('Press Enter to start push-to-talk (Ctrl-C to quit): ')
            released = Event()
            failure: list[Exception] = []

            def capture() -> None:
                try:
                    audio.capture_once(released)
                except Exception as error:  # surfaced at the terminal and diagnostics boundary
                    failure.append(error)

            worker = Thread(target=capture, name='buddy-terminal-ptt', daemon=False)
            worker.start()
            input('Recording. Press Enter to transcribe now: ')
            released.set()
            worker.join()
            worker = None
            released = None
            if failure:
                node.get_logger().error(f'push-to-talk capture failed: {failure[0]}')
                continue
            node.process_next_capture()
    except KeyboardInterrupt:
        pass
    finally:
        if released is not None:
            released.set()
        if worker is not None:
            worker.join()
        audio.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
