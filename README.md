# Buddy

Buddy is a Gazebo-first ROS 2 differential-drive robot with a local, voice-first
assistant.

The initial bounded implementation round is integrated. It provides a native
Gazebo Harmonic robot, deterministic safety and motion control, Navigation2
boundaries, a capability-based task executive, local voice/model adapter
boundaries, root bringup, and cross-layer tests. Concrete microphone, wake-word,
STT, LLM, TTS, and physical-hardware providers remain the next integration
slice.

## Documentation

- [Project idea](docs/buddy-idea.md)
- [Software architecture](docs/buddy-architecture.md)
- [Frozen ROS contract](docs/contracts/README.md)
- [Implementation status and limitations](docs/implementation-status.md)
- [Integrated validation report](docs/validation-report.md)

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

## Run the simulation

```bash
source install/setup.bash
ros2 launch buddy_bringup simulation.launch.py \
  use_sim_time:=true localization_mode:=mapping
```

Use `localization_mode:=saved map:=/absolute/path/to/map.yaml` for a saved map.
When running multiple Gazebo sessions on one host, give each session a unique
`GZ_PARTITION` and `ROS_DOMAIN_ID`.

## Test

```bash
ROS_LOG_DIR=/tmp/buddy-test-logs colcon test --ctest-args --output-on-failure
colcon test-result --verbose
```
