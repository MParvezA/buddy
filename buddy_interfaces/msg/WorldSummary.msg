# Low-rate semantic summary. Geometry-heavy data remains in standard ROS topics.

std_msgs/Header header
bool robot_pose_valid
geometry_msgs/PoseStamped robot_pose
string current_location
buddy_interfaces/NamedLocation[] named_locations
buddy_interfaces/ObjectObservation[] objects

