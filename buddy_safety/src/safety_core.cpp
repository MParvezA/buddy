// Copyright 2026 SyncRobot

#include "buddy_safety/safety_core.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

#include "buddy_safety/command_arbiter_core.hpp"

namespace buddy_safety
{

namespace
{

constexpr std::int64_t kNanosecondsPerSecond = 1000000000LL;
constexpr double kPi = 3.14159265358979323846;

builtin_interfaces::msg::Time time_from_nanoseconds(const std::int64_t time_ns)
{
  builtin_interfaces::msg::Time stamp;
  const std::int64_t nonnegative_ns = std::max<std::int64_t>(0, time_ns);
  stamp.sec = static_cast<std::int32_t>(nonnegative_ns / kNanosecondsPerSecond);
  stamp.nanosec = static_cast<std::uint32_t>(nonnegative_ns % kNanosecondsPerSecond);
  return stamp;
}

double approach(const double current, const double target, const double maximum_change)
{
  return current + std::clamp(target - current, -maximum_change, maximum_change);
}

bool finite_positive(const double value)
{
  return std::isfinite(value) && value > 0.0;
}

}  // namespace

SafetyCore::SafetyCore(const SafetyConfig & config, const std::int64_t start_steady_ns)
: config_(config),
  start_steady_ns_(start_steady_ns),
  last_evaluation_steady_ns_(start_steady_ns)
{
  if (!finite_positive(config_.max_linear_velocity) ||
    !finite_positive(config_.max_angular_velocity) ||
    !finite_positive(config_.max_linear_acceleration) ||
    !finite_positive(config_.max_angular_acceleration))
  {
    throw std::invalid_argument("velocity and acceleration limits must be finite and positive");
  }
  if (!finite_positive(config_.obstacle_stop_distance) ||
    !finite_positive(config_.obstacle_slowdown_distance) ||
    config_.obstacle_slowdown_distance <= config_.obstacle_stop_distance)
  {
    throw std::invalid_argument(
            "obstacle slowdown distance must exceed the positive stop distance");
  }
  if (!finite_positive(config_.obstacle_front_arc_radians) ||
    config_.obstacle_front_arc_radians > 2.0 * kPi)
  {
    throw std::invalid_argument("obstacle front arc must be in (0, 2*pi]");
  }
  if (config_.command_timeout_ns <= 0 || config_.scan_timeout_ns <= 0 ||
    config_.controller_diagnostics_timeout_ns <= 0 ||
    config_.future_tolerance_ns < 0 || config_.startup_inhibit_ns < 0)
  {
    throw std::invalid_argument("timeouts are invalid");
  }
}

bool SafetyCore::submit_command(
  const geometry_msgs::msg::TwistStamped & command,
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns,
  std::string * const rejection_reason)
{
  if (!CommandArbiterCore::valid_stamp(
      command.header.stamp, now_ros_ns, config_.command_timeout_ns,
      config_.future_tolerance_ns))
  {
    if (rejection_reason != nullptr) {
      *rejection_reason = "timestamp is zero, stale, malformed, or too far in the future";
    }
    return false;
  }
  if (!std::isfinite(command.twist.linear.x) || !std::isfinite(command.twist.angular.z)) {
    if (rejection_reason != nullptr) {
      *rejection_reason = "linear.x and angular.z must be finite";
    }
    return false;
  }

  command_ = geometry_msgs::msg::TwistStamped();
  command_.header = command.header;
  command_.twist.linear.x = command.twist.linear.x;
  command_.twist.angular.z = command.twist.angular.z;
  command_seen_ = true;
  command_received_steady_ns_ = now_steady_ns;
  return true;
}

bool SafetyCore::submit_scan(
  const sensor_msgs::msg::LaserScan & scan,
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns,
  std::string * const rejection_reason)
{
  scan_seen_ = true;
  scan_received_steady_ns_ = now_steady_ns;
  last_scan_stamp_ = scan.header.stamp;
  last_scan_valid_ = false;
  nearest_obstacle_ = std::numeric_limits<double>::infinity();

  if (!CommandArbiterCore::valid_stamp(
      scan.header.stamp, now_ros_ns, config_.scan_timeout_ns, config_.future_tolerance_ns))
  {
    if (rejection_reason != nullptr) {
      *rejection_reason = "scan timestamp is zero, stale, malformed, or too far in the future";
    }
    return false;
  }
  if (scan.ranges.empty() || !std::isfinite(scan.angle_min) ||
    !finite_positive(scan.angle_increment) || !std::isfinite(scan.range_min) ||
    !finite_positive(scan.range_max) || scan.range_max <= scan.range_min)
  {
    if (rejection_reason != nullptr) {
      *rejection_reason = "scan geometry or range bounds are invalid";
    }
    return false;
  }

  const double half_arc = config_.obstacle_front_arc_radians / 2.0;
  bool monitored_sample_seen = false;
  for (std::size_t index = 0; index < scan.ranges.size(); ++index) {
    const double angle = static_cast<double>(scan.angle_min) +
      static_cast<double>(index) * static_cast<double>(scan.angle_increment);
    const double normalized_angle = std::atan2(std::sin(angle), std::cos(angle));
    if (std::abs(normalized_angle) > half_arc) {
      continue;
    }

    const double range = static_cast<double>(scan.ranges[index]);
    if (std::isinf(range) && range > 0.0) {
      monitored_sample_seen = true;
    } else if (std::isfinite(range) && range >= scan.range_min && range <= scan.range_max) {
      monitored_sample_seen = true;
      nearest_obstacle_ = std::min(nearest_obstacle_, range);
    }
  }

  if (!monitored_sample_seen) {
    if (rejection_reason != nullptr) {
      *rejection_reason = "scan has no valid samples in the configured front arc";
    }
    return false;
  }

  last_scan_valid_ = true;
  return true;
}

void SafetyCore::set_controller_health(
  const bool healthy,
  const std::int64_t now_steady_ns)
{
  controller_status_seen_ = true;
  controller_status_healthy_ = healthy;
  controller_status_received_steady_ns_ = now_steady_ns;
}

void SafetyCore::set_physical_emergency_stop_active(const bool active)
{
  physical_emergency_stop_active_ = active;
  if (active) {
    emergency_stop_latched_ = true;
    emergency_source_ = "physical_emergency_stop";
    emergency_message_ = "physical emergency stop is active";
  }
}

void SafetyCore::latch_emergency_stop(
  const buddy_interfaces::msg::EmergencyStopRequest & request)
{
  emergency_stop_latched_ = true;
  emergency_source_ = request.source.empty() ? "emergency_stop_request" : request.source;
  emergency_message_ = request.reason.empty() ? "emergency stop requested" : request.reason;
}

bool SafetyCore::reset_emergency_stop(
  const bool operator_acknowledged,
  const bool source_allowed,
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns,
  std::string * const result_message)
{
  if (!operator_acknowledged) {
    if (result_message != nullptr) {
      *result_message = "reset rejected: operator acknowledgment is required";
    }
    return false;
  }
  if (!source_allowed) {
    if (result_message != nullptr) {
      *result_message = "reset rejected: source is not allowed";
    }
    return false;
  }
  if (physical_emergency_stop_active_) {
    if (result_message != nullptr) {
      *result_message = "reset rejected: physical emergency stop is active";
    }
    return false;
  }
  if (!scan_healthy(now_ros_ns, now_steady_ns)) {
    if (result_message != nullptr) {
      *result_message = "reset rejected: required safety sensor is unhealthy";
    }
    return false;
  }
  if (!controller_healthy(now_steady_ns)) {
    if (result_message != nullptr) {
      *result_message = "reset rejected: controller is unhealthy";
    }
    return false;
  }

  emergency_stop_latched_ = false;
  emergency_source_ = "emergency_stop_request";
  emergency_message_ = "emergency stop requested";
  if (result_message != nullptr) {
    *result_message = "emergency stop latch cleared";
  }
  return true;
}

SafetyDecision SafetyCore::evaluate(
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns)
{
  if (emergency_stop_latched_) {
    return stopped(
      now_ros_ns, now_steady_ns,
      buddy_interfaces::msg::SafetyState::STATE_EMERGENCY_STOPPED,
      buddy_interfaces::msg::SafetyState::REASON_EMERGENCY_REQUEST,
      emergency_source_, emergency_message_);
  }
  if (now_steady_ns - start_steady_ns_ < config_.startup_inhibit_ns) {
    return stopped(
      now_ros_ns, now_steady_ns, buddy_interfaces::msg::SafetyState::STATE_SOFT_STOPPED,
      buddy_interfaces::msg::SafetyState::REASON_STARTUP_INHIBIT,
      "startup_inhibit", "startup motion inhibit is active");
  }
  if (!controller_healthy(now_steady_ns)) {
    return stopped(
      now_ros_ns, now_steady_ns, buddy_interfaces::msg::SafetyState::STATE_FAULT,
      buddy_interfaces::msg::SafetyState::REASON_CONTROLLER_FAULT,
      "controller_watchdog", "controller health is missing, stale, or faulted");
  }
  if (!scan_healthy(now_ros_ns, now_steady_ns)) {
    return stopped(
      now_ros_ns, now_steady_ns, buddy_interfaces::msg::SafetyState::STATE_FAULT,
      buddy_interfaces::msg::SafetyState::REASON_SENSOR_UNHEALTHY,
      "scan_watchdog", "required safety scan is missing, stale, or invalid");
  }
  if (!command_fresh(now_ros_ns, now_steady_ns)) {
    return stopped(
      now_ros_ns, now_steady_ns, buddy_interfaces::msg::SafetyState::STATE_SOFT_STOPPED,
      buddy_interfaces::msg::SafetyState::REASON_COMMAND_TIMEOUT,
      "command_watchdog", "arbitrated command is missing or stale");
  }

  const bool obstacle_stops =
    nearest_obstacle_ <= config_.obstacle_stop_distance &&
    (config_.obstacle_stop_all_motion || command_.twist.linear.x > 0.0);
  if (obstacle_stops) {
    return stopped(
      now_ros_ns, now_steady_ns, buddy_interfaces::msg::SafetyState::STATE_SOFT_STOPPED,
      buddy_interfaces::msg::SafetyState::REASON_COLLISION_RISK,
      "obstacle_monitor", "obstacle is inside the stop distance");
  }

  double desired_linear = std::clamp(
    command_.twist.linear.x, -config_.max_linear_velocity, config_.max_linear_velocity);
  double desired_angular = std::clamp(
    command_.twist.angular.z, -config_.max_angular_velocity, config_.max_angular_velocity);
  bool limited =
    desired_linear != command_.twist.linear.x || desired_angular != command_.twist.angular.z;
  bool obstacle_limited = false;

  if (desired_linear > 0.0 && nearest_obstacle_ < config_.obstacle_slowdown_distance) {
    const double scale = std::clamp(
      (nearest_obstacle_ - config_.obstacle_stop_distance) /
      (config_.obstacle_slowdown_distance - config_.obstacle_stop_distance),
      0.0, 1.0);
    desired_linear *= scale;
    if (config_.obstacle_scale_angular) {
      desired_angular *= scale;
    }
    limited = true;
    obstacle_limited = true;
  }

  const std::int64_t elapsed_ns = std::max<std::int64_t>(
    0, now_steady_ns - last_evaluation_steady_ns_);
  const double elapsed_seconds =
    static_cast<double>(elapsed_ns) / static_cast<double>(kNanosecondsPerSecond);
  const double linear_output = approach(
    last_linear_output_, desired_linear,
    config_.max_linear_acceleration * elapsed_seconds);
  const double angular_output = approach(
    last_angular_output_, desired_angular,
    config_.max_angular_acceleration * elapsed_seconds);
  limited = limited || linear_output != desired_linear || angular_output != desired_angular;

  last_linear_output_ = linear_output;
  last_angular_output_ = angular_output;
  last_evaluation_steady_ns_ = now_steady_ns;

  SafetyDecision decision;
  decision.output.header = command_.header;
  decision.output.header.stamp = time_from_nanoseconds(now_ros_ns);
  decision.output.twist.linear.x = linear_output;
  decision.output.twist.angular.z = angular_output;
  decision.state = limited ?
    buddy_interfaces::msg::SafetyState::STATE_LIMITED :
    buddy_interfaces::msg::SafetyState::STATE_NORMAL;
  decision.reason_code = obstacle_limited ?
    buddy_interfaces::msg::SafetyState::REASON_COLLISION_RISK :
    buddy_interfaces::msg::SafetyState::REASON_NONE;
  decision.motion_permitted = true;
  decision.emergency_stop_latched = false;
  decision.source = obstacle_limited ? "obstacle_monitor" : "safety_filter";
  decision.message = obstacle_limited ? "obstacle slowdown active" :
    (limited ? "configured motion limits active" : "motion permitted");
  return decision;
}

bool SafetyCore::emergency_stop_latched() const
{
  return emergency_stop_latched_;
}

bool SafetyCore::scan_healthy(
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns) const
{
  if (!config_.require_scan) {
    return true;
  }
  if (!scan_seen_ || !last_scan_valid_) {
    return false;
  }
  if (!CommandArbiterCore::valid_stamp(
      last_scan_stamp_, now_ros_ns, config_.scan_timeout_ns, config_.future_tolerance_ns))
  {
    return false;
  }
  const std::int64_t receipt_age_ns = now_steady_ns - scan_received_steady_ns_;
  return receipt_age_ns >= 0 && receipt_age_ns <= config_.scan_timeout_ns;
}

bool SafetyCore::controller_healthy(const std::int64_t now_steady_ns) const
{
  if (!config_.require_controller_diagnostics) {
    return true;
  }
  if (!controller_status_seen_ || !controller_status_healthy_) {
    return false;
  }
  const std::int64_t receipt_age_ns =
    now_steady_ns - controller_status_received_steady_ns_;
  return receipt_age_ns >= 0 &&
         receipt_age_ns <= config_.controller_diagnostics_timeout_ns;
}

bool SafetyCore::command_fresh(
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns) const
{
  if (!command_seen_) {
    return false;
  }
  if (!CommandArbiterCore::valid_stamp(
      command_.header.stamp, now_ros_ns, config_.command_timeout_ns,
      config_.future_tolerance_ns))
  {
    return false;
  }
  const std::int64_t receipt_age_ns = now_steady_ns - command_received_steady_ns_;
  return receipt_age_ns >= 0 && receipt_age_ns <= config_.command_timeout_ns;
}

SafetyDecision SafetyCore::stopped(
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns,
  const std::uint8_t state,
  const std::uint16_t reason,
  const std::string & source,
  const std::string & message)
{
  last_linear_output_ = 0.0;
  last_angular_output_ = 0.0;
  last_evaluation_steady_ns_ = now_steady_ns;

  SafetyDecision decision;
  decision.output.header.stamp = time_from_nanoseconds(now_ros_ns);
  decision.state = state;
  decision.reason_code = reason;
  decision.motion_permitted = false;
  decision.emergency_stop_latched = emergency_stop_latched_;
  decision.source = source;
  decision.message = message;
  return decision;
}

}  // namespace buddy_safety
