# Buddy: Implementation Status

## Scope

This document records the first contract-frozen implementation round. The
source of truth for ROS names, schemas, TF ownership, QoS, capabilities, and
safety behavior remains [docs/contracts](contracts/README.md).

The central trust boundary is implemented as:

```text
recognized utterance
  → bounded dialogue proposal
  → capability and argument validation
  → task action
  → named navigation action
  → Nav2 stamped velocity request
  → command arbiter
  → safety filter
  → Gazebo differential-drive input
```

Voice and AI packages have no movement publishers. The safety processes do not
depend on voice, dialogue, or task execution.

## Package inventory

| Layer | Packages | Implemented responsibility |
| --- | --- | --- |
| Shared contract | `buddy_interfaces` | Frozen messages, services, and actions |
| Simulation/hardware | `buddy_description`, `buddy_gazebo`, `buddy_hardware` | URDF/Xacro, native Harmonic SDF, sensors, differential drive, future driver boundary |
| Safety/motion | `buddy_base`, `buddy_safety` | Configuration, arbitration, limits, watchdogs, obstacle stop, latched emergency stop |
| Navigation/world | `buddy_navigation`, `buddy_localization`, `buddy_mapping`, `buddy_perception`, `buddy_world_model` | Nav2, EKF, SLAM/saved-map boundaries, named locations, summarized world state |
| Task execution | `buddy_capabilities`, `buddy_task_executor` | Frozen capability catalogue, schema validation, sequencing, feedback, cancellation, timeouts |
| Dialogue | `buddy_brain` | Summarized context, replaceable local-model adapter, strict JSON validation, confirmation |
| Voice | `buddy_voice` | Push-to-talk, replaceable wake/STT/TTS adapters, deterministic spoken emergency stop |
| Composition | `buddy_bringup` | Full launch, robot status aggregation, integration fixtures and tests |

## Implemented capabilities

- `stop`
- `speak`
- `navigate_to`
- `report_status`

Unknown capabilities, extra or missing arguments, incorrect types, invalid
timeouts, and unconfirmed plans are rejected before a robot-side action.

## Safety behavior

The only controller path is:

```text
/buddy/motion/request/{source}
  → /buddy/motion/arbitrated_cmd_vel
  → /buddy/motion/safe_cmd_vel
  → private Gazebo drive command
```

The arbiter owns fixed source priorities. Both the arbiter and safety filter
stop stale commands. The safety filter independently enforces velocity and
acceleration limits, scan health, obstacle slowdown/stop, controller health
in production, and a latched emergency stop. Production motion requires a
fresh, exact-name `buddy_base_controller` diagnostic heartbeat; a missing,
error-level, or steady-time-stale heartbeat enters controller fault and
publishes zero. Emergency reset requires an
allowed source, operator acknowledgement, released physical input, and healthy
required inputs. Obstacle handling is directional for forward and reverse
translation and requires all-around clearance for rotation. A second watchdog
inside the Gazebo process forces the controller input to zero if the ROS
adapter disappears. The adapter reports its own command-publication health, so
loss of that bridge is visible both to safety policy and diagnostics.

The navigation velocity boundary opens only while the registered named
navigation action owner emits its status heartbeat. Its 50 ms heartbeat and
200 ms steady-time lease close authorization independently of Nav2 command
freshness if the adapter process disappears. A persistent private Nav2 command
therefore cannot keep the robot moving after owner loss.

Task execution retains ownership of lower actions until a terminal result is
observed. An unconfirmed cancellation is quarantined and escalated through the
latched emergency-stop contract. Status, world, capability, and action-neighbor
readiness use steady-time liveness where authorization is safety-relevant;
paused simulation time cannot preserve stale authorization.

Voice capture and speech-recognition provider exceptions are converted to
structured error diagnostics and the input process remains recoverable.
Navigation ownership publishes startup, live, normal-close, and lease-timeout
diagnostics, including the private velocity-gate state.

## Deliberate limitations

- Production adapters for openWakeWord, whisper.cpp, llama.cpp, and Piper are
  not selected or installed yet. Deterministic local fakes exercise the same
  boundaries without cloud APIs.
- Push-to-talk has a software provider boundary but no desktop button or
  microphone device adapter yet.
- Named locations come from a static YAML file. There is no teach-location UI.
- Initial perception reports sensor readiness and summarized pose/location. The
  frozen round has no observation-ingress topic, so object observations are not
  populated yet.
- Battery state is explicitly unknown until a hardware or simulated battery
  interface is added.
- The physical emergency input is represented by the safety node boundary; no
  GPIO or motor-power interlock driver exists yet.
- Gazebo uses its native Harmonic smoke world. The AWS RoboMaker small-house
  world targets older Gazebo Classic conventions and was not added as a hidden
  compatibility dependency.
- The simulated drive uses Gazebo Harmonic's differential-drive system as the
  controller-equivalent implementation. Future hardware can replace it behind
  the same upper ROS interfaces.
- The RGB camera is present, but object recognition, person following, docking,
  and manipulation are outside this slice.
- Workspace tests must currently run with `colcon test --executor sequential`
  because concurrent discovery-based package tests reuse the frozen global ROS
  action names.
- ROS 2 Jazzy action-process teardown uses version-scoped private rclpy task
  registries and worker-pool state. Replace that workaround when a future rclpy
  release provides a complete public drain API.

## Recommended next vertical slice

Connect one end-to-end local voice path without expanding robot authority:

1. Add a desktop push-to-talk microphone provider.
2. Add a whisper.cpp STT adapter.
3. Add a llama.cpp completion adapter that can return only the frozen JSON
   proposal schema.
4. Add Piper synthesis/playback.
5. Keep deterministic fakes for CI and add provider contract tests.
6. Demonstrate only `speak`, `report_status`, and confirmed `navigate_to` in the
   existing Gazebo world.

This slice should not change movement topics, controller access, safety
semantics, or capability validation.

The build, test, Gazebo, end-to-end, and safety evidence for this implementation
round is recorded in [the validation report](validation-report.md).
