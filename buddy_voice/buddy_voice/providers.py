"""
Replaceable audio, wake-word, STT, and TTS provider boundaries.

Concrete openWakeWord, whisper.cpp, and Piper adapters intentionally do not
live here until their native dependencies are selected and installed.  The
fakes below make the ROS components deterministic in simulation and tests.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Event
import time
from typing import Protocol, Sequence


@dataclass(frozen=True)
class AudioCapture:
    """One bounded audio capture supplied by an input provider."""

    samples: bytes
    input_mode: int
    locale: str = 'en-US'


@dataclass(frozen=True)
class Transcript:
    """A recognized interim or final transcript."""

    text: str
    confidence: float
    is_final: bool
    locale: str = 'en-US'


@dataclass(frozen=True)
class SynthesizedSpeech:
    """Synthesized local audio represented by its deterministic duration."""

    duration_seconds: float


class AudioInputProvider(Protocol):
    """Supplies bounded captures to the voice node."""

    def next_capture(self) -> AudioCapture | None:
        """Return the next completed capture, or ``None`` when idle."""


class WakeWordProvider(Protocol):
    """Boundary for a future streaming wake-word engine."""

    def detected(self, samples: bytes) -> bool:
        """Return whether the supplied audio contains the configured wake word."""


class SpeechToTextProvider(Protocol):
    """Converts a bounded capture into ordered interim/final transcripts."""

    def transcribe(self, capture: AudioCapture) -> Sequence[Transcript]:
        """Transcribe one capture without publishing ROS messages directly."""


class TextToSpeechProvider(Protocol):
    """
    Synthesizes local speech through a cooperative bounded call boundary.

    Implementations must return, raise :class:`SpeechSynthesisCancelled`, or
    raise :class:`SpeechSynthesisTimeout` once ``cancel_event`` is set or
    ``deadline_monotonic`` is reached.  This deliberately keeps a slow native
    TTS engine out of a detached worker thread: a stuck provider must not keep
    the action server alive after cancellation or shutdown.
    """

    def synthesize(
            self,
            text: str,
            voice: str,
            *,
            cancel_event: Event,
            deadline_monotonic: float) -> SynthesizedSpeech:
        """Return audio metadata or raise one of the bounded-call errors."""


class SpeechSynthesisError(RuntimeError):
    """A provider could not synthesize the requested speech."""


class SpeechSynthesisCancelled(SpeechSynthesisError):
    """A cooperative provider stopped after its action was cancelled."""


class SpeechSynthesisTimeout(SpeechSynthesisError):
    """A cooperative provider reached the action's steady-clock deadline."""


class PushToTalkAudioInput:
    """
    Usable initial audio input path driven by an explicit button event.

    Hardware/UI code calls :meth:`push_completed_capture` when push-to-talk is
    released.  The node consumes only completed bounded captures, avoiding a
    hidden microphone or cloud dependency in the first implementation.
    """

    def __init__(self) -> None:
        self._captures: deque[AudioCapture] = deque()

    def push_completed_capture(
            self, samples: bytes, locale: str = 'en-US') -> None:
        """Queue audio captured during one push-to-talk interaction."""
        self._captures.append(AudioCapture(samples, 0, locale))

    def next_capture(self) -> AudioCapture | None:
        """Return the next completed push-to-talk capture."""
        return self._captures.popleft() if self._captures else None


class FakeAudioInput(PushToTalkAudioInput):
    """Deterministic push-to-talk audio source for tests and simulation."""

    def submit(self, samples: bytes = b'fake-audio', locale: str = 'en-US') -> None:
        """Add one deterministic completed capture."""
        self.push_completed_capture(samples, locale)


class FakeWakeWordProvider:
    """Deterministic wake-word boundary that matches configured byte payloads."""

    def __init__(self, matching_samples: set[bytes] | None = None) -> None:
        self._matching_samples = matching_samples or set()

    def detected(self, samples: bytes) -> bool:
        """Return true only for exact configured fake samples."""
        return samples in self._matching_samples


class FakeSpeechToTextProvider:
    """Returns preconfigured transcript batches in capture order."""

    def __init__(self, batches: Sequence[Sequence[Transcript]] | None = None) -> None:
        self._batches: deque[Sequence[Transcript]] = deque(batches or [])
        self.captures: list[AudioCapture] = []

    def transcribe(self, capture: AudioCapture) -> Sequence[Transcript]:
        """Record the capture and return the next configured transcript batch."""
        self.captures.append(capture)
        return self._batches.popleft() if self._batches else []


class FakeTextToSpeechProvider:
    """Deterministic, cooperative local TTS fake for tests and simulation."""

    def __init__(
            self,
            duration_seconds: float = 0.06,
            fail_for: set[str] | None = None,
            *,
            synthesis_delay_seconds: float = 0.0,
            unexpected_for: set[str] | None = None) -> None:
        self.duration_seconds = duration_seconds
        self.fail_for = fail_for or set()
        self.synthesis_delay_seconds = max(0.0, synthesis_delay_seconds)
        self.unexpected_for = unexpected_for or set()
        self.requests: list[tuple[str, str]] = []

    def synthesize(
            self,
            text: str,
            voice: str,
            *,
            cancel_event: Event,
            deadline_monotonic: float) -> SynthesizedSpeech:
        """Return a fixed result while observing cancellation and deadlines."""
        self.requests.append((text, voice))
        delay_deadline = time.monotonic() + self.synthesis_delay_seconds
        while time.monotonic() < delay_deadline:
            if cancel_event.is_set():
                raise SpeechSynthesisCancelled('fake TTS synthesis cancelled')
            if time.monotonic() >= deadline_monotonic:
                raise SpeechSynthesisTimeout('fake TTS synthesis timed out')
            cancel_event.wait(min(
                0.01,
                delay_deadline - time.monotonic(),
                max(0.0, deadline_monotonic - time.monotonic()),
            ))
        if cancel_event.is_set():
            raise SpeechSynthesisCancelled('fake TTS synthesis cancelled')
        if time.monotonic() >= deadline_monotonic:
            raise SpeechSynthesisTimeout('fake TTS synthesis timed out')
        if text in self.fail_for:
            raise SpeechSynthesisError('fake TTS synthesis failure')
        if text in self.unexpected_for:
            raise RuntimeError('fake unexpected TTS provider error')
        return SynthesizedSpeech(self.duration_seconds)
