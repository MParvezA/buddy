# Buddy Gazebo Harmonic layer

This package owns the native Gazebo Harmonic simulation model and its bounded
ROS launch fragment. It deliberately uses the installed Harmonic systems
`gz::sim::systems::DiffDrive` and `JointStatePublisher`: `gz_ros2_control` is
not installed in this development environment. The model therefore remains a
supported Gazebo-native equivalent rather than pretending to provide a
`ros2_control` hardware plugin.

`safe_cmd_vel_adapter` is the only ROS-to-simulation motion boundary. It
subscribes only to `/buddy/motion/safe_cmd_vel`
(`geometry_msgs/msg/TwistStamped`, reliable depth 1) and publishes Gazebo's
private `/model/buddy/watchdog/input`. The in-process `CommandWatchdog` system
publishes `/model/buddy/watchdog/output` at 50 Hz and forces zero after 250 ms
without fresh input; native DiffDrive subscribes only to that filtered topic.
There is no direct DiffDrive command topic exposed by this package. The future physical
`diff_drive_controller` configuration is in `buddy_description/config` and
uses Jazzy's native `TwistStamped` command interface, `cmd_vel_timeout: 0.25`, and
`enable_odom_tf: false`; the eventual physical hardware plugin must be wired
to that controller with its private `~/cmd_vel` remapped only from the frozen
safe command topic.

The bridge maps `/clock`, `/joint_states`, `/odom/wheel`, `/scan`,
`/imu/data_raw`, `/camera/image_raw`, and `/camera/camera_info`. Sensor and
wheel-state streams use the `SENSOR_DATA` profile (best effort, volatile);
`/odom/wheel` overrides the publisher queue to KeepLast(10).
Gazebo also produces native bumper contacts at `bumper/contacts`; no frozen ROS
bumper message/topic exists yet, so it is not bridged. The bridge never maps
Gazebo's pose / TF stream, so it cannot compete with the contract-owned
`odom -> base_link` EKF TF.

Run headlessly after building:

```bash
source install/setup.bash
bash buddy_gazebo/test/headless_smoke.sh
/usr/bin/python3 buddy_gazebo/test/runtime_contract_smoke.py
/usr/bin/python3 buddy_gazebo/test/runtime_watchdog_smoke.py
```

The smoke world is intentionally small and native to Harmonic. It does not
clone or vendor the Gazebo Classic/Dashing AWS small-house world.

The runtime contract smoke automatically selects isolated `ROS_DOMAIN_ID` and
`GZ_PARTITION` values. It verifies exact lidar, IMU, and camera frame IDs,
advancing monotonic simulation time, `odom` / `base_link` wheel odometry, and
the robot-state-publisher static sensor TF chain.
The watchdog smoke commands motion, terminates the sole ROS/Gazebo adapter,
and verifies odometry becomes stationary after the in-process timeout.

The adapter imports the system Gazebo Python bindings supplied by Debian
packages `python3-gz-msgs10` and `python3-gz-transport13`. They are runtime
prerequisites for this native-Gazebo path; no matching ROS package or rosdep
key is installed in this workspace.
