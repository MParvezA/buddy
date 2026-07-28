# Integration and Validation Contract

## Worker test boundary

Every workstream must be independently testable using fakes for unavailable
neighbors. Worker branches include only tests under their owned package paths.

The root owns cross-package integration tests and full-system launch files.

## Required worker evidence

- Package build succeeds.
- Unit and component tests pass.
- Public interfaces match the frozen contract.
- Changed paths match the workstream allowlist.
- No test is disabled or weakened.
- Assumptions and limitations are reported.

## Sequential integration order

1. `buddy_interfaces`
2. Gazebo and hardware abstraction
3. Safety and motion
4. Navigation and perception
5. Task executive and capabilities
6. AI and dialogue
7. Voice
8. Root-owned bringup and integration tests

After every integration, rebuild the affected package closure and run its tests.

## Full-system validation

- Full workspace build and test.
- Dependency graph contains no cycles.
- TF tree has one owner per dynamic transform.
- Gazebo spawns Buddy and publishes simulated time.
- Joint, odometry, lidar, IMU, and camera topics appear.
- Teleoperation reaches the controller only through arbiter and safety.
- Stale motion requests result in zero output.
- Conflicting sources follow fixed priority.
- Emergency stop overrides every source and remains latched.
- AI and voice nodes have no velocity publishers.
- Unknown tasks and arguments are rejected.
- Navigation cancellation ends in a safe stopped state.
- Navigation can operate without AI.
- Emergency stop operates without voice, AI, or task execution.
- The supported end-to-end voice-to-navigation flow succeeds.
- Unknown and unreachable locations return structured failures.

## Test world decision

The first smoke test uses a small native Gazebo Harmonic world owned by
`buddy_gazebo`.

The AWS RoboMaker Small House World `ros2` branch targets Gazebo Classic and ROS
Dashing-era launch conventions. It is an optional future environment after its
world and model assets are validated or converted for Gazebo Harmonic. The
initial test suite must not depend on that conversion.

