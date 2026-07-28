# ROS Interface Contract

All names in this document are absolute graph names under `/buddy`, except
standard ROS topics such as `/tf`, `/map`, and `/diagnostics`.

## Voice

| Name | Type | ROS interface |
| --- | --- | --- |
| `/buddy/voice/utterance` | Topic | `buddy_interfaces/msg/RecognizedUtterance` |
| `/buddy/voice/speak` | Action | `buddy_interfaces/action/Speak` |

The deterministic stop detector publishes an
`EmergencyStopRequest` directly to the safety request topic. It does not wait
for dialogue or task execution.

## AI and task execution

| Name | Type | ROS interface |
| --- | --- | --- |
| `/buddy/tasks/execute` | Action | `buddy_interfaces/action/ExecuteTask` |
| `/buddy/capabilities/list` | Service | `buddy_interfaces/srv/ListCapabilities` |
| `/buddy/status` | Topic | `buddy_interfaces/msg/RobotStatus` |
| `/buddy/world/summary` | Topic | `buddy_interfaces/msg/WorldSummary` |

The AI is an action client of `/buddy/tasks/execute`. The task executive is the
only server. Receiving a goal does not imply acceptance: the task executive
validates the plan and may reject it.

## Navigation and semantic world

| Name | Type | ROS interface |
| --- | --- | --- |
| `/buddy/navigation/navigate_to_named_location` | Action | `buddy_interfaces/action/NavigateToNamedLocation` |
| `/buddy/world/resolve_named_location` | Service | `buddy_interfaces/srv/ResolveNamedLocation` |

The navigation capability resolves a semantic name to a `map`-frame pose and
uses Nav2's standard `nav2_msgs/action/NavigateToPose` action internally.

## Motion path

All motion-request topics use `geometry_msgs/msg/TwistStamped`.

| Name | Publisher |
| --- | --- |
| `/buddy/motion/request/navigation` | Navigation |
| `/buddy/motion/request/teleop` | Teleoperation |
| `/buddy/motion/request/docking` | Docking capability |
| `/buddy/motion/request/recovery` | Bounded recovery |
| `/buddy/motion/arbitrated_cmd_vel` | Command arbiter only |
| `/buddy/motion/safe_cmd_vel` | Safety filter only |

The differential-drive controller's private `~/cmd_vel` input is remapped only
from `/buddy/motion/safe_cmd_vel`.

No other publisher or remap to the controller input is allowed.

## Safety and diagnostics

| Name | Type | ROS interface |
| --- | --- | --- |
| `/buddy/safety/emergency_stop/request` | Topic | `buddy_interfaces/msg/EmergencyStopRequest` |
| `/buddy/safety/emergency_stop/reset` | Service | `buddy_interfaces/srv/ResetEmergencyStop` |
| `/buddy/safety/state` | Topic | `buddy_interfaces/msg/SafetyState` |
| `/diagnostics` | Topic | `diagnostic_msgs/msg/DiagnosticArray` |

## Standard sensor and state interfaces

| Name | Type |
| --- | --- |
| `/joint_states` | `sensor_msgs/msg/JointState` |
| `/odom/wheel` | `nav_msgs/msg/Odometry` |
| `/odometry/filtered` | `nav_msgs/msg/Odometry` |
| `/scan` | `sensor_msgs/msg/LaserScan` |
| `/imu/data_raw` | `sensor_msgs/msg/Imu` |
| `/camera/image_raw` | `sensor_msgs/msg/Image` |
| `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` |
| `/map` | `nav_msgs/msg/OccupancyGrid` |
| `/tf` and `/tf_static` | `tf2_msgs/msg/TFMessage` |
| `/clock` | `rosgraph_msgs/msg/Clock` |

## Parameter and namespace rules

- Nodes use the `/buddy` namespace unless they provide a standard global ROS
  interface.
- Topic names are parameters only when the frozen default remains unchanged.
- Frame IDs do not begin with `/`.
- Nodes do not construct topic names from model-generated text.

