# Buddy: Software Architecture

## Document status

- Status: Initial architecture
- Scope: Gazebo-first implementation with a future physical robot
- Architectural priority: Deterministic safety around probabilistic AI

For the project vision, product goals, and roadmap, see
[buddy-idea.md](buddy-idea.md).

The implementation-level ROS contract is maintained in
[docs/contracts](contracts/README.md).

## 1. Core design rule

The local AI model decides **what Buddy should attempt**. Deterministic robotics
software decides **how to perform it safely**.

The AI model must not:

- Send commands directly to the wheels.
- Publish raw velocity commands.
- Implement collision avoidance.
- Override emergency-stop or safety conditions.
- Execute arbitrary programs or unregistered robot actions.

Instead, the model proposes structured tasks from a bounded capability list. A
policy validator checks each proposal before a task executive can run it.
Navigation, motor control, and safety continue to operate when the AI process is
slow, unavailable, or incorrect.

## 2. System overview

```text
┌──────────────────────────────────────────┐
│ Voice interface                          │
│ Wake word → speech-to-text → speech      │
├──────────────────────────────────────────┤
│ AI and dialogue                          │
│ Understand request → propose task plan   │
├──────────────────────────────────────────┤
│ Policy validator and task executive      │
│ Validate → sequence → monitor → cancel   │
├──────────────────────────────────────────┤
│ Navigation, perception, and world model  │
│ Localization, maps, paths, objects       │
├──────────────────────────────────────────┤
│ Safety, arbitration, and motion control  │
│ Limits, watchdogs, collision prevention  │
├──────────────────────────────────────────┤
│ Gazebo or physical hardware              │
│ Wheels, encoders, lidar, IMU, camera     │
└──────────────────────────────────────────┘
```

These boundaries separate components with different timing and reliability
requirements. Speech and AI may take seconds. Motor control and safety require
predictable responses and cannot wait for the AI.

## 3. Voice interface

Responsibilities:

- Capture microphone audio.
- Apply noise suppression and, later, acoustic echo cancellation.
- Detect the "Hey Buddy" wake phrase.
- Convert speech to text.
- Send recognized text to the dialogue layer.
- Convert responses to speech.
- Recognize emergency phrases through a fast, non-LLM path.

The voice layer produces text or a semantic request. It never produces wheel
commands.

Possible ROS packages:

```text
buddy_audio
buddy_wake_word
buddy_speech_to_text
buddy_text_to_speech
```

## 4. AI and dialogue

Responsibilities:

- Interpret natural-language requests.
- Ask for clarification when necessary.
- Maintain bounded conversational context.
- Read a summarized robot and world state.
- Propose structured tasks.
- Explain progress and results.

An example task proposal is:

```json
{
  "tasks": [
    {
      "capability": "navigate_to",
      "arguments": {
        "location": "kitchen"
      }
    },
    {
      "capability": "speak",
      "arguments": {
        "message": "I have arrived in the kitchen."
      }
    }
  ]
}
```

The AI receives a compact context rather than raw ROS topics or sensor streams:

```json
{
  "mode": "idle",
  "location": "living_room",
  "battery_percent": 71,
  "localization": "good",
  "available_capabilities": [
    "navigate_to",
    "speak",
    "report_status"
  ]
}
```

The model runtime should be isolated in a separate process. Restarting or losing
that process must not stop safety monitoring, navigation cancellation, or manual
control.

Possible ROS packages:

```text
buddy_llm
buddy_dialogue
buddy_context_builder
```

## 5. Policy validator

The validator is the trust boundary between generated decisions and robot
actions. It checks:

- Whether the capability is registered.
- Whether arguments conform to the capability schema.
- Whether named places and objects exist.
- Whether the robot is localized and operational.
- Whether the operation is allowed in the current mode.
- Whether battery and sensor health are sufficient.
- Whether an emergency stop or other safety lock is active.
- Whether explicit user confirmation is required.

Invalid or unsafe proposals are rejected and returned to the dialogue layer as
structured errors.

Possible ROS package:

```text
buddy_policy
```

## 6. Task executive and capability registry

The task executive:

- Runs approved tasks in sequence.
- Tracks progress and timeouts.
- Supports cancellation.
- Selects bounded recovery behavior.
- Reports structured results.

Long-running robot operations should use ROS 2 actions because they support a
goal, feedback, cancellation, and a final result.

Each capability has an explicit contract:

```text
Name: navigate_to
Input: Named location or map pose
Preconditions: Localized, mobile, no emergency stop
Feedback: Planning, moving, blocked, recovering
Result: Arrived, cancelled, unreachable, failed
```

Possible ROS packages:

```text
buddy_interfaces
buddy_capabilities
buddy_task_executor
```

## 7. Navigation

Responsibilities:

- Maintain wheel odometry.
- Fuse odometry and IMU measurements.
- Build a map.
- Localize Buddy within a saved map.
- Plan global paths.
- Avoid local obstacles.
- Recover from blocked or invalid paths.
- Dock to a charging station in a later phase.

Navigation2 receives goals from validated capabilities and outputs velocity
requests to the command arbiter. It does not communicate directly with the AI
model.

Possible ROS packages:

```text
buddy_localization
buddy_mapping
buddy_navigation
```

## 8. Perception and world model

Perception responsibilities:

- Process lidar and proximity data.
- Process camera images.
- Detect and track people or objects in later phases.
- Report observations with confidence and timestamps.

Buddy maintains two related representations:

- A geometric world model containing walls, obstacles, free space, and robot
  pose for navigation.
- A semantic world model containing room names, known locations, people, and
  objects for capabilities and dialogue.

The AI consumes a controlled summary of the semantic world model. Navigation
consumes the geometric model.

Possible ROS packages:

```text
buddy_perception
buddy_world_model
```

## 9. Command arbitration and safety

Every movement source passes through one command arbiter:

```text
Nav2 velocity ─────┐
Teleoperation ─────┼──→ command arbiter → safety filter → drive controller
Docking controller ┤
Manual recovery ───┘
```

The arbiter grants control to exactly one source according to an explicit
priority policy. The safety filter then applies:

- Linear and angular velocity limits.
- Acceleration limits.
- Obstacle-based slowdown and stopping.
- Command timeouts.
- Emergency-stop state.
- Required sensor-health checks.
- Restricted areas.
- A motor-command watchdog.

Only the safety-filtered output reaches the differential-drive controller.

Emergency handling must not depend on the AI. Physical emergency-stop input,
collision danger, motor faults, localization loss, and command timeout can
always stop the robot.

Possible ROS packages:

```text
buddy_command_arbiter
buddy_safety
buddy_collision_monitor
buddy_base_controller
```

## 10. Simulation and hardware abstraction

Gazebo and future physical hardware should expose equivalent ROS interfaces:

```text
                   ┌── Gazebo wheels and sensors
Upper layers ──────┤
                   └── Physical drivers and motor controller
```

Both implementations should provide, where applicable:

- Joint states
- Wheel odometry
- Lidar scans
- IMU measurements
- Camera images
- Contact or bumper state
- Battery status
- A differential-drive command interface

This boundary allows the voice, AI, task, navigation, and safety layers to move
from simulation to hardware without being redesigned.

Possible ROS packages:

```text
buddy_description
buddy_gazebo
buddy_hardware
buddy_bringup
```

## 11. System supervisor and diagnostics

A deterministic supervisor tracks operational readiness and major modes:

- `BOOTING`
- `IDLE`
- `ACTIVE`
- `DOCKING`
- `LOW_BATTERY`
- `DEGRADED`
- `FAULT`
- `EMERGENCY_STOP`

It monitors:

- Sensor availability
- Localization quality
- Navigation health
- AI process availability
- Battery state
- Motor-controller connection
- Compute load and temperature
- Emergency-stop state

The supervisor distinguishes optional failures from motion-critical failures.
For example, Buddy can remain safely stationary and accept manual stop commands
when conversational AI is unavailable.

Possible ROS packages:

```text
buddy_supervisor
buddy_diagnostics
```

## 12. Internal communication rules

Use ROS 2 communication types according to their semantics:

- Topics for continuous streams such as sensors, state, diagnostics, and
  velocity requests.
- Services for short, immediate queries or configuration operations.
- Actions for cancellable work that takes time and reports progress.

Interfaces between important layers should use structured messages rather than
free-form text. Free-form language belongs at the human/AI boundary. Validated
capability requests belong at the AI/robot boundary.

## 13. Suggested ROS workspace structure

```text
buddy_ws/src/
├── buddy_interfaces/
├── buddy_description/
├── buddy_gazebo/
├── buddy_bringup/
├── buddy_base/
├── buddy_safety/
├── buddy_localization/
├── buddy_navigation/
├── buddy_perception/
├── buddy_world_model/
├── buddy_capabilities/
├── buddy_task_executor/
├── buddy_voice/
├── buddy_brain/
└── buddy_diagnostics/
```

These are architectural ownership boundaries, not a requirement to create every
package immediately. The first implementation should introduce packages only
as their responsibilities become real.

## 14. Example command flow

For "Hey Buddy, come to the kitchen":

1. The wake-word component detects "Hey Buddy."
2. Speech-to-text produces the user's sentence.
3. The AI proposes `navigate_to(kitchen)`.
4. The policy validator checks the capability, location, and robot state.
5. The task executive invokes the navigation capability.
6. Navigation2 calculates a path and velocity requests.
7. The command arbiter grants Nav2 control.
8. The safety layer filters every requested velocity.
9. The differential-drive controller moves the simulated wheels.
10. Navigation reports arrival.
11. The task executive reports success.
12. Buddy announces, "I have arrived in the kitchen."

If the AI process fails after navigation begins, the task executive can cancel
or safely complete the bounded task. If danger appears, the safety layer reacts
without waiting for the AI.

## 15. Safety invariants

The following rules must remain true throughout development:

- The AI cannot command wheel velocities.
- All movement commands pass through arbitration and safety filtering.
- Emergency stop is independent of AI and dialogue services.
- Stale movement commands result in stopping.
- Long-running tasks are cancellable.
- Unknown capabilities and invalid arguments are rejected.
- Loss of motion-critical sensors prevents autonomous motion.
- Simulation and physical hardware share the same upper-layer contracts.
