# TF, Simulation Time, and QoS Contract

## TF ownership

Only one node owns each dynamic transform.

| Transform | Owner |
| --- | --- |
| `map` → `odom` | SLAM Toolbox while mapping, or localization while using a saved map |
| `odom` → `base_link` | `robot_localization` EKF |
| `base_link` → wheel and sensor frames | `robot_state_publisher` from URDF |

The differential-drive controller publishes wheel odometry on `/odom/wheel` but
is configured with `enable_odom_tf: false` to prevent a second
`odom` → `base_link` publisher.

Gazebo's internal world pose is not published as a competing ROS localization
transform.

Required initial sensor frames:

- `base_link`
- `base_footprint`
- `left_wheel_link`
- `right_wheel_link`
- `caster_link`
- `lidar_link`
- `imu_link`
- `camera_link`
- `camera_optical_frame`

## Simulation time

- Every simulation-aware node declares or accepts `use_sim_time`.
- Integrated Gazebo launches set `use_sim_time: true`.
- Gazebo is the sole source of simulation clock time.
- `ros_gz_bridge` bridges `/clock` unidirectionally from Gazebo to ROS.
- Hardware launches set `use_sim_time: false`.
- Timeouts use ROS time for simulated behavior and steady time where wall-clock
  liveness must remain meaningful while simulation is paused.

## QoS profiles

| Data class | History/depth | Reliability | Durability |
| --- | --- | --- | --- |
| Lidar, IMU, camera | Keep last 5 | Best effort | Volatile |
| Wheel odometry | Keep last 10 | Best effort | Volatile |
| Motion requests and outputs | Keep last 1 | Reliable | Volatile |
| Emergency-stop requests | Keep last 10 | Reliable | Volatile |
| Safety state | Keep last 1 | Reliable | Transient local |
| Robot status | Keep last 1 | Reliable | Transient local |
| World summary | Keep last 1 | Reliable | Transient local |
| Recognized utterances | Keep last 10 | Reliable | Volatile |
| Map | Keep last 1 | Reliable | Transient local |
| Diagnostics | Keep last 10 | Reliable | Volatile |

ROS actions and services use their standard reliable QoS profiles.

Transient safety state ensures a late-joining consumer immediately learns that
motion is inhibited. Emergency-stop requests remain events; the authoritative
latched condition is `/buddy/safety/state`.

