# Repository Inventory

Inventory date: 2026-07-28

## Initial repository state

- The workspace initially contained only:
  - `docs/buddy-idea.md`
  - `docs/buddy-architecture.md`
- No ROS packages, build system, tests, CI, or Git repository existed.
- The root coordinator initialized Git so parallel work can use isolated
  branches and worktrees.

## Available environment

- Ubuntu 24.04
- ROS 2 Jazzy
- Gazebo Sim 8.11
- CMake 3.28
- System Python 3.12
- `colcon`

Verified installed ROS packages:

- `ros_gz_sim`
- `ros_gz_bridge`
- `controller_manager`
- `diff_drive_controller`
- `nav2_bringup`
- `slam_toolbox`
- `robot_localization`
- `xacro`
- `robot_state_publisher`

## Build-environment constraint

The interactive shell places a user-installed Python 3.10 before system Python.
ROS Jazzy's Python modules are installed for Python 3.12. Builds therefore use:

```bash
colcon build --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
```

Workers must preserve this selection in their validation commands.

## Existing user changes

The two initial design documents are user-requested content and must be
preserved. There were no existing source changes or generated packages.

## Test-world evaluation

The referenced AWS RoboMaker Small House World is licensed MIT-0 and provides a
useful multi-room environment. Its `ros2` branch uses Gazebo Classic commands,
ROS Dashing setup instructions, and Classic launch conventions.

Decision for the first implementation round:

- Do not make the initial Gazebo Harmonic smoke test depend on this world.
- Build a minimal native Harmonic world for deterministic CI and smoke tests.
- Keep the AWS world as a later, optional conversion and navigation test asset.

## Provisional hardware-independent choices

Exact chassis dimensions, wheel dimensions, sensor models, motor limits, and
onboard compute are not yet product decisions. Workstreams may use documented
simulation defaults, but they must keep those values configurable and must not
encode them into cross-layer message schemas.

