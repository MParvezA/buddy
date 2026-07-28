"""ROS-independent bounded semantic store."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Location:
    """Validated map-frame named location."""

    name: str
    description: str
    enabled: bool
    x: float
    y: float
    z: float
    qx: float
    qy: float
    qz: float
    qw: float


class SemanticStore:
    """Immutable named locations plus bounded, replace-by-id observations."""

    def __init__(self, locations: list[Location], max_observations: int = 50) -> None:
        self._locations = {item.name.casefold(): item for item in locations}
        if len(self._locations) != len(locations):
            raise ValueError('named locations must be unique ignoring case')
        self._observations: dict[str, Any] = {}
        self._max_observations = max_observations

    @classmethod
    def from_yaml(cls, path: str | Path, max_observations: int = 50):
        """Load and validate named locations from YAML."""
        data = yaml.safe_load(Path(path).read_text()) or {}
        if data.get('frame_id') != 'map':
            raise ValueError('named locations must use the map frame')
        parsed = []
        for raw in data.get('locations', []):
            name = str(raw.get('name', '')).strip()
            if not name:
                raise ValueError('named location name must not be empty')
            position = raw.get('position', {})
            orientation = raw.get('orientation', {})
            values = [
                position.get('x', 0.0),
                position.get('y', 0.0),
                position.get('z', 0.0),
                orientation.get('x', 0.0),
                orientation.get('y', 0.0),
                orientation.get('z', 0.0),
                orientation.get('w', 1.0),
            ]
            parsed.append(
                Location(
                    name=name,
                    description=str(raw.get('description', '')),
                    enabled=bool(raw.get('enabled', True)),
                    x=float(values[0]),
                    y=float(values[1]),
                    z=float(values[2]),
                    qx=float(values[3]),
                    qy=float(values[4]),
                    qz=float(values[5]),
                    qw=float(values[6]),
                )
            )
        return cls(parsed, max_observations=max_observations)

    @property
    def locations(self) -> tuple[Location, ...]:
        """Return locations in deterministic display order."""
        return tuple(sorted(self._locations.values(), key=lambda item: item.name.casefold()))

    @property
    def observations(self) -> tuple[Any, ...]:
        """Return current bounded observations."""
        return tuple(self._observations.values())

    def resolve(self, name: str) -> Location | None:
        """Resolve a case-insensitive semantic name."""
        return self._locations.get(name.strip().casefold())

    def record_observation(self, observation_id: str, observation: Any) -> None:
        """Replace by ID and evict oldest insertion when the boundary is full."""
        key = observation_id.strip()
        if not key:
            raise ValueError('observation_id must not be empty')
        if key not in self._observations and len(self._observations) >= self._max_observations:
            oldest = next(iter(self._observations))
            del self._observations[oldest]
        self._observations[key] = observation
