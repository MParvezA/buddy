# Buddy hardware boundary

This package does **not** implement physical motor, encoder, lidar, IMU,
camera, battery, or emergency-stop drivers. It records the stable boundary a
later `ros2_control` hardware plugin and sensor-driver set must meet:

- velocity command interfaces for `left_wheel_joint` and `right_wheel_joint`;
- position and velocity state interfaces for both wheels;
- `buddy_base_controller` receives only `/buddy/motion/safe_cmd_vel` as a
  `geometry_msgs/msg/TwistStamped` command, with a 250 ms timeout;
- wheel odometry is `/odom/wheel` and does not publish `odom -> base_link` TF;
- frozen sensor topics and frames in `config/hardware_interfaces.yaml`.

Physical driver selection, transport protocols, electrical interlocks, battery
measurement, and physical emergency-stop integration remain intentionally
unimplemented. A physical launch must set `use_sim_time: false`.
