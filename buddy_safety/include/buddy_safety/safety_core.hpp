// Copyright 2026 SyncRobot

#ifndef BUDDY_SAFETY__SAFETY_CORE_HPP_
#define BUDDY_SAFETY__SAFETY_CORE_HPP_

#include <cstdint>
#include <limits>
#include <string>

#include "buddy_interfaces/msg/emergency_stop_request.hpp"
#include "buddy_interfaces/msg/safety_state.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"

namespace buddy_safety
{

struct SafetyConfig
{
  double max_linear_velocity{0.5};
  double max_angular_velocity{1.0};
  double max_linear_acceleration{0.75};
  double max_angular_acceleration{1.5};
  double obstacle_stop_distance{0.25};
  double obstacle_slowdown_distance{0.6};
  double obstacle_front_arc_radians{1.0471975512};
  double obstacle_rear_arc_radians{1.0471975512};
  bool obstacle_stop_all_motion{true};
  bool obstacle_scale_angular{true};
  bool require_scan{true};
  bool require_controller_diagnostics{false};
  std::int64_t command_timeout_ns{250000000};
  std::int64_t scan_timeout_ns{500000000};
  std::int64_t controller_diagnostics_timeout_ns{500000000};
  std::int64_t future_tolerance_ns{100000000};
  std::int64_t startup_inhibit_ns{500000000};
};

struct SafetyDecision
{
  geometry_msgs::msg::TwistStamped output;
  std::uint8_t state{buddy_interfaces::msg::SafetyState::STATE_SOFT_STOPPED};
  std::uint16_t reason_code{buddy_interfaces::msg::SafetyState::REASON_STARTUP_INHIBIT};
  bool motion_permitted{false};
  bool emergency_stop_latched{false};
  std::string source{"safety_filter"};
  std::string message{"startup inhibit"};
};

class SafetyCore
{
public:
  explicit SafetyCore(const SafetyConfig & config, std::int64_t start_steady_ns = 0);

  bool submit_command(
    const geometry_msgs::msg::TwistStamped & command,
    std::int64_t now_ros_ns,
    std::int64_t now_steady_ns,
    std::string * rejection_reason = nullptr);

  bool submit_scan(
    const sensor_msgs::msg::LaserScan & scan,
    std::int64_t now_ros_ns,
    std::int64_t now_steady_ns,
    std::string * rejection_reason = nullptr);

  void set_controller_health(bool healthy, std::int64_t now_steady_ns);
  void set_physical_emergency_stop_active(bool active);
  void latch_emergency_stop(const buddy_interfaces::msg::EmergencyStopRequest & request);

  bool reset_emergency_stop(
    bool operator_acknowledged,
    bool source_allowed,
    std::int64_t now_ros_ns,
    std::int64_t now_steady_ns,
    std::string * result_message);

  SafetyDecision evaluate(std::int64_t now_ros_ns, std::int64_t now_steady_ns);

  bool emergency_stop_latched() const;

private:
  bool scan_healthy(std::int64_t now_ros_ns, std::int64_t now_steady_ns) const;
  bool controller_healthy(std::int64_t now_steady_ns) const;
  bool command_fresh(std::int64_t now_ros_ns, std::int64_t now_steady_ns) const;
  SafetyDecision stopped(
    std::int64_t now_ros_ns,
    std::int64_t now_steady_ns,
    std::uint8_t state,
    std::uint16_t reason,
    const std::string & source,
    const std::string & message);

  SafetyConfig config_;
  std::int64_t start_steady_ns_;
  std::int64_t last_evaluation_steady_ns_;

  geometry_msgs::msg::TwistStamped command_;
  bool command_seen_{false};
  std::int64_t command_received_steady_ns_{0};

  bool scan_seen_{false};
  bool last_scan_valid_{false};
  builtin_interfaces::msg::Time last_scan_stamp_;
  std::int64_t scan_received_steady_ns_{0};
  double nearest_front_obstacle_{std::numeric_limits<double>::infinity()};
  double nearest_rear_obstacle_{std::numeric_limits<double>::infinity()};
  double nearest_obstacle_all_around_{std::numeric_limits<double>::infinity()};

  bool controller_status_seen_{false};
  bool controller_status_healthy_{true};
  std::int64_t controller_status_received_steady_ns_{0};

  bool physical_emergency_stop_active_{false};
  bool emergency_stop_latched_{false};
  std::string emergency_source_{"emergency_stop_request"};
  std::string emergency_message_{"emergency stop requested"};

  double last_linear_output_{0.0};
  double last_angular_output_{0.0};
};

}  // namespace buddy_safety

#endif  // BUDDY_SAFETY__SAFETY_CORE_HPP_
