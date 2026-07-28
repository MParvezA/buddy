"""Steady-time raw sensor readiness tracking without recognition."""

from dataclasses import dataclass


SENSORS = ('scan', 'imu', 'image', 'camera_info')


@dataclass(frozen=True)
class Readiness:
    """Snapshot of raw-sensor availability."""

    ready: bool
    missing: tuple[str, ...]
    stale: tuple[str, ...]
    invalid_frames: tuple[str, ...]


class SensorTracker:
    """Track last receipt using caller-provided monotonic timestamps."""

    def __init__(self) -> None:
        self._last_seen: dict[str, float] = {}
        self._frames: dict[str, str] = {}

    def observe(self, sensor: str, frame_id: str, received_at: float) -> None:
        """Record a raw sensor sample without interpreting its contents."""
        if sensor not in SENSORS:
            raise ValueError(f'unknown sensor: {sensor}')
        self._last_seen[sensor] = received_at
        self._frames[sensor] = frame_id.strip()

    def readiness(self, now: float, timeout: float) -> Readiness:
        """Evaluate liveness even when ROS simulation time is paused."""
        missing = tuple(sensor for sensor in SENSORS if sensor not in self._last_seen)
        stale = tuple(
            sensor
            for sensor in SENSORS
            if sensor in self._last_seen and now - self._last_seen[sensor] > timeout
        )
        invalid_frames = tuple(
            sensor
            for sensor in SENSORS
            if sensor in self._frames and not self._frames[sensor]
        )
        return Readiness(
            ready=not missing and not stale and not invalid_frames,
            missing=missing,
            stale=stale,
            invalid_frames=invalid_frames,
        )
