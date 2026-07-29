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
| Gazebo and hardware abstraction | `bfc21f6`, `4be3261`, `f3613d3`, `3d519f1`, `df065f3`, `9528d32` |
| Safety and motion | `c5d14e6`, `cf4d17b`, `c75c587`, `639d817` |
| Navigation and perception | `3797b0b`, `263efbe`, `9c513cf`, `e935c90`, `23ad465`, `d41a58b`, `f300e10`, `9dc5595`, `91eb8ef`, `fda8b19`, `53a6835` |
| Task executive and capabilities | `8161ece`, `50ff4cf`, `d5416de`, `ed7ca8a`, `d23059d`, `0982a5d`, `d70863f`, `d96fa10`, `6c3315e`, `6a0488e`, `822e9fd`, `9f4c9a3` |
| AI and dialogue | `68e8b7b`, `82250e8`, `0182359`, `80bce6b`, `42e12d5` |
| Voice interface | `6eb4b01`, `643660d`, `0560f2e`, `e8cb596`, `f891fdf`, `261406b` |
| Root bringup and integration | `40057fa`, `a9c4156`, `81f7c39`, `b1283df`, `977ac46` |

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
ROS_LOG_DIR=/tmp/buddy_full_final_220 \
  ROS_DOMAIN_ID=220 GZ_PARTITION=buddy_full_final_220 \
  colcon test --executor sequential --event-handlers console_cohesion+ \
  --ctest-args --output-on-failure
colcon test-result --verbose
```

Results:

- 16 packages built successfully.
- 205 tests, zero errors, zero failures.
- 13 reported skips are the `buddy_safety` source files skipped by
  `ament_cppcheck` because the installed cppcheck 2.13 is blacklisted by the
  ROS Jazzy wrapper for known performance problems. C++ compilation, GTest,
  cpplint, uncrustify, and the other configured linters passed.
- Workspace tests run sequentially because otherwise ROS package tests that
  intentionally use the frozen global action names can discover another
  package's simultaneously running mock servers. A parallel diagnostic run
  reproduced that harness collision with explicit duplicate-action-server
  warnings; the sequential full run is the uncontaminated validation mode.
- Topological package enumeration and the repository dependency-DAG test found
  no package cycle.
- Interface-generation and interface-shape checks passed.
- Repository boundary tests found no movement publisher in `buddy_brain` or
  `buddy_voice`.
- The dialogue layer reports ready only after capability discovery and its
  speech/task action neighbors are live. Loss of the capability registry
  revokes its cached authorization.
- The task executive reports ready only with fresh robot status, fresh world
  state, and live navigation/speech actions. Its one-second steady-time leases
  expire even if simulation time is paused.
- Voice-provider failures and navigation-ownership transitions publish
  structured diagnostics and recover without process restart.
- Production safety requires the exact `buddy_base_controller` diagnostic.
  A missing, error-level, or steady-time-stale heartbeat enters controller
  fault independently of simulation time.

## Gazebo, TF, and simulation-time evidence

The isolated native Harmonic runtime contract probe passed with:

- Advancing, monotonic `/clock`.
- `/scan` in `lidar_link`.
- `/imu/data_raw` in `imu_link`.
- Camera image and camera info in `camera_optical_frame`.
- Wheel odometry as `odom → base_link`.
- Static transforms from the base through all sensor frames.
- One parent for every TF child, including `base_link → base_footprint`.
- Wheel-odometry QoS as KeepLast(10), best effort, volatile.
- A Gazebo-process command watchdog which forces its private drive input to
  zero if the ROS adapter stops updating it.

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

The final integration test waits on structured dialogue and task-executive
readiness diagnostics rather than a fixed startup delay. This closed a
reproducible full-suite race in which a discoverable task action server could
still lack the status/world inputs required to authorize navigation.

Action-boundary regression suites additionally prove that an aborted ROS
action carrying its default custom success value cannot be interpreted as
success by navigation, task execution, dialogue, or voice. Submission,
result, cancellation, and provider exceptions become structured failures.
Cancellation is reported only after the lower action reaches terminal
`STATUS_CANCELED`; an unconfirmed stop is an explicit failure.

A production Nav2 run accepted the real `kitchen` named goal, generated
non-zero navigation requests, and moved the Gazebo robot from approximately
`x=0.0` to `x=1.04`. It entered bounded Nav2 recovery in the minimal smoke
world; the test therefore does not claim terminal arrival at `kitchen`.

## Safety evidence

The final production runtime probes in isolated domains 221 and 222 passed:

- Teleoperation won over a simultaneous lower-priority navigation command.
- Navigation resumed after the teleoperation command became stale.
- Controller odometry showed physical simulated movement.
- A stale movement command produced zero safe output.
- Emergency stop latched and overrode movement.
- Reset required the frozen operator acknowledgement procedure.
- Forward motion uses the front obstacle arc, reverse motion uses the rear
  arc, and in-place rotation requires safe all-around scan coverage.
- Loss of the sole ROS-to-Gazebo command adapter stopped physical simulation:
  the final probe moved `0.460 m`, then moved `0.000 m` after watchdog expiry
  while commands continued to be published on the disconnected ROS side.
- Loss of the named-navigation owner closed the private Nav2 velocity gate in
  `0.241 s`; acceleration-limited safe output reached zero in `0.537 s` while
  a persistent command continued on the private Nav2 topic.
- Loss of the base-controller adapter expired its required diagnostic,
  transitioned safety to `REASON_CONTROLLER_FAULT`, forced the safe output to
  zero in `0.491 s`, and made `RobotStatus.motion_ready` false.

Unit and component tests additionally prove velocity/acceleration limits,
obstacle stop and slowdown, malformed-command rejection, controller and sensor
watchdogs, fixed arbitration priorities, physical-input latching, and reset
preconditions. These tests launch safety and navigation without voice,
dialogue, or task processes, demonstrating that safe stopping and navigation
boundaries do not depend on the AI stack.

If a lower action does not acknowledge cancellation or reach a terminal result
inside its bound, the task executive retains ownership, admits only the
registered stop capability, and publishes the frozen latched emergency-stop
request. It never reports the possibly live action as drained.

The voice, task, and navigation action processes now drain active work,
retrieve or cancel queued Jazzy callbacks, finite-join the executor worker
pool, and destroy waitables in order. The final motion-traffic production
launch shut every ROS process down cleanly with no unretrieved-future,
`Destroyable`, failed-to-terminate, SIGTERM-escalation, or SIGKILL event.

## Contract changes and rejected workarounds

- No frozen contract changed after version `0.1.0` was marked FROZEN.
- A mapping regression that directly read the Gazebo SDF was rejected and
  replaced with a mapping-owned frozen-range assertion.
- No adapter was added to bypass arbitration, safety filtering, capability
  validation, or package dependency direction.
- Runtime frame, mapping-bound, cancellation, and Jazzy teardown findings were
  fixed inside their owning packages.
- Independent review findings for reverse collision coverage, simulator-side
  stale-command stopping, odometry QoS, TF parent uniqueness, action transport
  status handling, and exception-safe teardown were fixed without changing
  frozen interfaces.
- The final review round additionally corrected incomplete all-around lidar
  coverage, stale navigation-owner authorization, unconfirmed lower-action
  ownership, readiness liveness, and unobserved dialogue speech results without
  changing a frozen contract.
- The final invariant-10 review findings were closed in their owning packages:
  voice provider exceptions now emit structured diagnostics, navigation leases
  report startup/live/closed/timeout transitions, and the Gazebo command
  adapter publishes the controller heartbeat required by production safety.

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
  workaround using rclpy's private task registries and Python worker pool.
  Re-evaluate it when upgrading ROS 2.
- The complete workspace test command must use `--executor sequential` until
  each discovery-based component test receives a separate DDS domain.
- `robot_state_publisher` warns that KDL ignores inertia on the root
  `base_link`; TF publication and simulation dynamics are unaffected, but a
  future description cleanup can introduce a massless parser root.

## Local-provider follow-up

The CPU-only push-to-talk, whisper.cpp, llama.cpp, and Piper slice was
implemented after this contract-frozen baseline. Its build, live-provider,
resource, integration, and safety evidence is recorded in
[the local-provider validation report](local-provider-validation.md).

The next vertical slice is continuous local wake-word detection, audio ducking,
and a repeatable English/German test under an enforced 8 GB/four-core resource
limit. It must keep the movement path, safety semantics, and
capability-validation boundary unchanged.
