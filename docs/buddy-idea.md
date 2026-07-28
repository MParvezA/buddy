# Buddy: Project Idea

## Document status

- Status: Initial concept
- Scope: Gazebo-first robot development
- Target platform: Differential-drive mobile robot
- Primary interaction: Local, voice-first assistant

For the system design that supports this idea, see
[buddy-architecture.md](buddy-architecture.md).

## 1. Vision

Buddy is a differential-drive mobile robot that acts as a local, voice-first
assistant: a private, movable alternative to a smart speaker.

A person should be able to speak naturally to Buddy:

- "Hey Buddy, come to the kitchen."
- "Follow me."
- "What is blocking the hallway?"
- "Go to your charging station."
- "Stop."

Buddy should understand the request, select an approved robot capability,
perform it safely, and respond through speech.

The initial implementation will run in Gazebo so that movement, sensing,
navigation, and failure behavior can be developed before physical hardware is
selected.

## 2. Feasibility

The project is feasible when developed incrementally:

- A simulated differential-drive robot is highly feasible.
- Autonomous navigation in a simulated indoor environment is feasible.
- Local speech recognition and speech generation are feasible.
- A local language model selecting from known robot capabilities is feasible.
- A dependable physical household robot is feasible but substantially harder.
- A general-purpose robot that invents arbitrary physical skills is not a
  realistic first target.

The robot mechanics and basic movement model are well understood. The greater
challenges are reliable localization, safe navigation, audio quality while
moving, controlled AI behavior, and transferring from simulation to physical
hardware.

## 3. Product principles

### 3.1 Local first

Speech recognition, language-model inference, and speech generation should be
capable of running locally. This improves privacy, reduces cloud dependence, and
allows the robot to retain basic functionality when internet access is absent.

### 3.2 Voice first

The main user interface should be natural speech rather than an application or
developer-facing API. Internal structured interfaces will still exist so that
the voice system can control Buddy safely and predictably.

### 3.3 Safety before intelligence

Buddy must remain safe when the AI model is slow, unavailable, or wrong.
Emergency stopping, collision prevention, motor limits, and command timeouts
must not depend on the language model.

### 3.4 Simulation before hardware

The software should be proven in Gazebo before committing to motors, sensors,
onboard compute, batteries, and chassis hardware.

### 3.5 Incremental capabilities

Buddy should begin with a small list of dependable abilities. Each new
capability should have explicit inputs, preconditions, feedback, cancellation,
and failure results.

## 4. Initial user experience

The desired interaction is:

1. The user says, "Hey Buddy."
2. Buddy indicates that it is listening.
3. The user gives a request.
4. Buddy confirms the interpreted task when appropriate.
5. Buddy performs the task while remaining interruptible.
6. Buddy reports success, cancellation, or failure in plain language.

Example:

> User: "Hey Buddy, come to the kitchen."
>
> Buddy: "Okay, I am coming to the kitchen."
>
> Buddy: "I have arrived."

The command "Stop" must receive immediate priority and must not wait for a
language-model response.

## 5. Initial capabilities

The first version should support only:

- `stop`
- `speak`
- `navigate_to`
- `report_status`

Later versions may add:

- `follow_person`
- `explore_area`
- `inspect_object`
- `dock`
- Reminders and timers
- Smart-home integration
- Object and person-related assistance

## 6. Initial technology direction

The conservative starting stack is:

- Ubuntu 24.04
- ROS 2 Jazzy
- Gazebo Harmonic
- `ros_gz` for ROS-Gazebo integration
- URDF/Xacro for the robot description
- `ros2_control` or the Gazebo differential-drive system for wheel control
- Navigation2 for path planning, localization, and obstacle avoidance
- SLAM Toolbox for map creation
- `robot_localization` for sensor fusion
- Python for orchestration and AI integration
- C++ where controller timing or performance requires it

The proposed local voice stack is:

- Wake-word detection: openWakeWord
- Speech-to-text: whisper.cpp
- Language-model inference: llama.cpp
- Text-to-speech: Piper

These are initial candidates rather than permanent dependencies. Components
should remain replaceable behind small internal interfaces.

## 7. Simulated robot

Buddy's initial simulated body should contain:

- Two powered wheels
- One or two passive caster wheels
- Wheel encoders
- A 2D lidar
- An IMU
- A front RGB or RGB-D camera
- Optional contact or bumper sensors

Gazebo does not initially need to simulate room acoustics. The microphone,
speech processing, and speaker can run on the development computer while Buddy
moves in simulation.

Push-to-talk should be implemented before wake-word detection. This separates
navigation problems from audio problems during early development.

## 8. Development roadmap

### Phase 1: Robot simulation

- Create the URDF/Xacro model.
- Add two powered wheels and a passive caster.
- Spawn Buddy in Gazebo.
- Support keyboard teleoperation.
- Publish joint states, transforms, and odometry.

### Phase 2: Sensors and safe motion

- Add lidar and IMU simulation.
- Add command arbitration.
- Add velocity limits, timeout, and emergency stop.
- Verify obstacle stopping independently of navigation.

### Phase 3: Autonomous navigation

- Add sensor fusion.
- Build and save a map.
- Localize Buddy in that map.
- Configure Navigation2.
- Navigate safely to selected map poses.

### Phase 4: Named capabilities

- Add named locations such as `kitchen` and `charging_station`.
- Implement the capability registry and task executive.
- Support `stop`, `speak`, `navigate_to`, and `report_status`.
- Test cancellation, unreachable goals, and failure reporting.

### Phase 5: Voice interface

- Begin with push-to-talk.
- Add local speech-to-text and text-to-speech.
- Add a deterministic spoken stop command.
- Add the "Hey Buddy" wake phrase.

### Phase 6: Local AI

- Run the local model in a separate process.
- Restrict model output to a task schema.
- Add policy validation.
- Add concise robot-state context.
- Test invalid, ambiguous, and unsafe requests.

### Phase 7: Perception and physical transfer

- Add camera-based capabilities as separate vertical features.
- Model realistic sensor noise and motion limits.
- Select onboard compute, motors, encoders, and sensors.
- Implement physical hardware drivers behind the simulation interfaces.

## 9. First acceptance target

The first end-to-end target is:

> Buddy receives a spoken destination, validates it, confirms it aloud,
> navigates there safely in Gazebo, and announces its arrival.

Acceptance requires:

- The destination is selected through a registered capability.
- The AI cannot command wheel velocities.
- Unknown locations are rejected.
- The task can be cancelled.
- "Stop" works without waiting for the AI.
- Obstacle avoidance and collision stopping are deterministic.
- Failure produces a clear spoken or logged result.

## 10. Primary risks

- Incorrect coordinate transforms between `map`, `odom`, `base_link`, and
  sensors.
- Inaccurate odometry and simulation-to-hardware differences.
- Poor Navigation2 tuning for Buddy's footprint and dynamics.
- Wake-word false activations and missed activations.
- Motor and speaker noise interfering with speech recognition.
- AI hallucinations becoming executable tasks without strict validation.
- AI latency interfering with interaction if processes are not isolated.
- Overloading the first version with perception and household capabilities.

These risks are controlled by keeping components replaceable, testing each
layer independently, and adding capabilities only after the safety and
navigation foundation is reliable.

## 11. References

- [ROS 2 Jazzy documentation](https://docs.ros.org/en/jazzy/)
- [Gazebo Harmonic documentation](https://gazebosim.org/docs/harmonic/getstarted/)
- [ROS-Gazebo integration (`ros_gz`)](https://docs.ros.org/en/jazzy/p/ros_gz/)
- [Navigation2 documentation](https://docs.nav2.org/)
- [openWakeWord](https://github.com/dscripka/openWakeWord)
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
- [llama.cpp](https://github.com/ggml-org/llama.cpp)
- [Piper](https://github.com/OHF-Voice/piper1-gpl)
