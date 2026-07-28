# Buddy Initial Implementation Validation

## Result

The contract-frozen initial implementation round is integrated and validated on
Ubuntu 24.04, ROS 2 Jazzy, and Gazebo Harmonic.

The implemented trust boundary is:

```text
recognized utterance
  → bounded structured proposal
  → capability and argument validation
  → task action
  → named navigation action
  → Nav2 velocity boundary
  → command arbiter
  → safety filter
  → private differential-drive controller input
```

The frozen contract remains version `0.1.0`. No worker changed a frozen topic,
action, service, TF, QoS, safety, or capability contract.

## Workstream commit map

| Workstream | Integrated commits |
| --- | --- |
| Shared contracts and interfaces | `e129077` |
| Gazebo and hardware abstraction | `bfc21f6`, `4be3261`, `f3613d3`, `3d519f1` |
| Safety and motion | `c5d14e6` |
| Navigation and perception | `3797b0b`, `263efbe`, `9c513cf`, `e935c90`, `23ad465`, `d41a58b` |
| Task executive and capabilities | `8161ece`, `50ff4cf`, `d5416de`, `ed7ca8a`, `d23059d`, `0982a5d`, `d70863f` |
| AI and dialogue | `68e8b7b`, `82250e8` |
| Voice interface | `6eb4b01`, `643660d` |
| Root bringup and integration | `40057fa` |

Integration followed the contract-first order: interfaces, Gazebo, safety,
navigation, task execution, dialogue, voice, and finally root bringup. Runtime
findings were returned to the owning workstream and integrated as bounded
follow-up commits.

## Packages and interfaces

The workspace contains 16 ROS packages:

- `buddy_interfaces`
- `buddy_description`, `buddy_gazebo`, `buddy_hardware`
- `buddy_base`, `buddy_safety`
- `buddy_navigation`, `buddy_localization`, `buddy_mapping`
- `buddy_perception`, `buddy_world_model`
- `buddy_capabilities`, `buddy_task_executor`
- `buddy_brain`, `buddy_voice`
- `buddy_bringup`

The generated shared package provides:

- Actions: `ExecuteTask`, `NavigateToNamedLocation`, and `Speak`.
- Services: `ListCapabilities`, `ResolveNamedLocation`, and
  `ResetEmergencyStop`.
- Structured utterance, task, capability, location, world, safety, status, and
  observation messages.

The exact ROS names, schemas, QoS, TF ownership, capability errors, arbitration
priorities, and emergency-stop semantics are in
[the frozen contract](contracts/README.md).

## Build and automated-test evidence

Final integrated commands:

```bash
colcon build --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
ROS_LOG_DIR=/tmp/buddy_full_definitive \
  ROS_DOMAIN_ID=203 GZ_PARTITION=buddy_full_definitive_203 \
  colcon test --event-handlers console_cohesion+ \
  --ctest-args --output-on-failure
colcon test-result --verbose
```

Results:

- 16 packages built successfully.
- 138 tests, zero errors, zero failures.
- 13 reported skips are the `buddy_safety` source files skipped by
  `ament_cppcheck` because the installed cppcheck 2.13 is blacklisted by the
  ROS Jazzy wrapper for known performance problems. C++ compilation, GTest,
  cpplint, uncrustify, and the other configured linters passed.
- Topological package enumeration and the repository dependency-DAG test found
  no package cycle.
- Interface-generation and interface-shape checks passed.
- Repository boundary tests found no movement publisher in `buddy_brain` or
  `buddy_voice`.

## Gazebo, TF, and simulation-time evidence

The isolated native Harmonic runtime contract probe passed with:

- Advancing, monotonic `/clock`.
- `/scan` in `lidar_link`.
- `/imu/data_raw` in `imu_link`.
- Camera image and camera info in `camera_optical_frame`.
- Wheel odometry as `odom → base_link`.
- Static transforms from the base through all sensor frames.

The full production launch reported Nav2 controller, planner, behavior-tree
navigator, and SLAM Toolbox in lifecycle state `active [3]`. Live TF lookup
resolved `map → base_link` repeatedly at advancing simulation timestamps.
Voice input, dialogue, and the navigation velocity boundary all reported
`use_sim_time=true`.

The production mapping run used an 8 m SLAM laser limit matching the simulated
lidar and a robot-centered global costmap. The final log audit found no
robot/sensor-origin-out-of-bounds or laser-range-exceeds warnings.

## End-to-end and failure evidence

The root launch test exercised real policy and safety layers with deterministic
Nav2 and speech fakes:

```text
recognized utterance
  → confirmation
  → validated task
  → named navigation
  → navigation velocity
  → arbitration
  → safety filtering
  → stopped terminal state
  → spoken task result
```

It also proved that an unknown location returns the structured
`OUTCOME_UNKNOWN_LOCATION` result and that navigation cancellation reaches a
confirmed canceled result with safe output at zero.

A production Nav2 run accepted the real `kitchen` named goal, generated
non-zero navigation requests, and moved the Gazebo robot from approximately
`x=0.0` to `x=1.04`. It entered bounded Nav2 recovery in the minimal smoke
world; the test therefore does not claim terminal arrival at `kitchen`.

## Safety evidence

The final production runtime probe in isolated domain 204 passed:

- Teleoperation won over a simultaneous lower-priority navigation command.
- Navigation resumed after the teleoperation command became stale.
- Controller odometry showed physical simulated movement.
- A stale movement command produced zero safe output.
- Emergency stop latched and overrode movement.
- Reset required the frozen operator acknowledgement procedure.

Unit and component tests additionally prove velocity/acceleration limits,
obstacle stop and slowdown, malformed-command rejection, controller and sensor
watchdogs, fixed arbitration priorities, physical-input latching, and reset
preconditions. These tests launch safety and navigation without voice,
dialogue, or task processes, demonstrating that safe stopping and navigation
boundaries do not depend on the AI stack.

Both long-running action layers now drain active goals and explicitly stop
queued Jazzy executor callbacks before destroying ROS entities. The final
motion-traffic launch shut down cleanly with no unretrieved-future,
`Destroyable`, SIGTERM, or SIGKILL escalation for either action layer.

## Contract changes and rejected workarounds

- No frozen contract changed after version `0.1.0` was marked FROZEN.
- A mapping regression that directly read the Gazebo SDF was rejected and
  replaced with a mapping-owned frozen-range assertion.
- No adapter was added to bypass arbitration, safety filtering, capability
  validation, or package dependency direction.
- Runtime frame, mapping-bound, cancellation, and Jazzy teardown findings were
  fixed inside their owning packages.

## Known limitations

The deliberate limitations in
[the implementation status](implementation-status.md) remain. In addition:

- The minimal smoke world and initial Nav2 tuning demonstrate real planning and
  motion but do not yet provide a repeatable terminal `kitchen` arrival.
- Gazebo Harmonic accepts the `gz_frame_id` sensor extension at runtime, while
  the core SDF checker prints schema warnings because that extension is outside
  the core SDF vocabulary.
- The Gazebo Ruby launcher reports its SIGINT exit as code `-2`; child ROS
  processes and the action layers shut down cleanly.
- The Jazzy action nodes contain a documented, version-scoped executor
  workaround using rclpy's private submitted-task registry. Re-evaluate it
  when upgrading ROS 2.

## Recommended next vertical slice

Connect the local audio/model providers without increasing robot authority:

1. Desktop push-to-talk and microphone capture.
2. whisper.cpp speech-to-text.
3. llama.cpp structured proposal generation constrained to the frozen schema.
4. Piper synthesis and playback.
5. Provider contract tests plus a repeatable small-world Nav2 arrival scenario.

Keep the movement path, safety semantics, and capability-validation boundary
unchanged.
