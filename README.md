# Buddy

Buddy is a Gazebo-first ROS 2 differential-drive robot with a local, voice-first
assistant.

The project is currently establishing its shared ROS contracts before the
individual architectural workstreams are implemented.

## Documentation

- [Project idea](docs/buddy-idea.md)
- [Software architecture](docs/buddy-architecture.md)
- [Frozen ROS contract](docs/contracts/README.md)

## Target environment

- Ubuntu 24.04
- ROS 2 Jazzy
- Gazebo Harmonic

## Build

```bash
source /opt/ros/jazzy/setup.bash
colcon build --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
```

The explicit Python selection prevents user-installed Python versions from being
mixed with ROS Jazzy's system Python 3.12 packages.
