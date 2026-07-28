// Copyright 2026 SyncRobot

#include "buddy_safety/command_arbiter_core.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>

namespace buddy_safety
{

namespace
{

constexpr std::int64_t kNanosecondsPerSecond = 1000000000LL;

bool finite_allowed_axes(const geometry_msgs::msg::TwistStamped & command)
{
  return std::isfinite(command.twist.linear.x) && std::isfinite(command.twist.angular.z);
}

geometry_msgs::msg::TwistStamped sanitize(const geometry_msgs::msg::TwistStamped & command)
{
  geometry_msgs::msg::TwistStamped result;
  result.header = command.header;
  result.twist.linear.x = command.twist.linear.x;
  result.twist.angular.z = command.twist.angular.z;
  return result;
}

}  // namespace

CommandArbiterCore::CommandArbiterCore(
  const std::int64_t command_timeout_ns,
  const std::int64_t future_tolerance_ns)
: command_timeout_ns_(command_timeout_ns),
  future_tolerance_ns_(future_tolerance_ns)
{
  if (command_timeout_ns_ <= 0) {
    throw std::invalid_argument("command timeout must be positive");
  }
  if (future_tolerance_ns_ < 0) {
    throw std::invalid_argument("future tolerance must not be negative");
  }
}

bool CommandArbiterCore::submit(
  const MotionSource source,
  const geometry_msgs::msg::TwistStamped & command,
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns,
  std::string * const rejection_reason)
{
  if (!valid_stamp(
      command.header.stamp, now_ros_ns, command_timeout_ns_, future_tolerance_ns_))
  {
    if (rejection_reason != nullptr) {
      *rejection_reason = "timestamp is zero, stale, malformed, or too far in the future";
    }
    return false;
  }

  if (!finite_allowed_axes(command)) {
    if (rejection_reason != nullptr) {
      *rejection_reason = "linear.x and angular.z must be finite";
    }
    return false;
  }

  samples_.at(static_cast<std::size_t>(source)) = Sample{sanitize(command), now_steady_ns};
  return true;
}

SelectedCommand CommandArbiterCore::select(
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns) const
{
  SelectedCommand selected;
  int selected_priority = std::numeric_limits<int>::min();

  for (std::size_t index = 0; index < samples_.size(); ++index) {
    const auto source = static_cast<MotionSource>(index);
    const auto & sample = samples_[index];
    if (sample.has_value() && fresh(*sample, now_ros_ns, now_steady_ns) &&
      priority(source) > selected_priority)
    {
      selected.has_source = true;
      selected.source = source;
      selected.command = sample->command;
      selected_priority = priority(source);
    }
  }
  return selected;
}

int CommandArbiterCore::priority(const MotionSource source)
{
  switch (source) {
    case MotionSource::kTeleop:
      return 200;
    case MotionSource::kDocking:
      return 150;
    case MotionSource::kRecovery:
      return 125;
    case MotionSource::kNavigation:
      return 100;
  }
  return 0;
}

const char * CommandArbiterCore::source_name(const MotionSource source)
{
  switch (source) {
    case MotionSource::kTeleop:
      return "teleop";
    case MotionSource::kDocking:
      return "docking";
    case MotionSource::kRecovery:
      return "recovery";
    case MotionSource::kNavigation:
      return "navigation";
  }
  return "unknown";
}

bool CommandArbiterCore::valid_stamp(
  const builtin_interfaces::msg::Time & stamp,
  const std::int64_t now_ros_ns,
  const std::int64_t maximum_age_ns,
  const std::int64_t future_tolerance_ns)
{
  if (stamp.sec < 0 || stamp.nanosec >= static_cast<std::uint32_t>(kNanosecondsPerSecond)) {
    return false;
  }

  const std::int64_t stamp_ns = stamp_to_nanoseconds(stamp);
  if (stamp_ns <= 0) {
    return false;
  }

  const std::int64_t age_ns = now_ros_ns - stamp_ns;
  return age_ns <= maximum_age_ns && age_ns >= -future_tolerance_ns;
}

std::int64_t CommandArbiterCore::stamp_to_nanoseconds(
  const builtin_interfaces::msg::Time & stamp)
{
  return static_cast<std::int64_t>(stamp.sec) * kNanosecondsPerSecond +
         static_cast<std::int64_t>(stamp.nanosec);
}

bool CommandArbiterCore::fresh(
  const Sample & sample,
  const std::int64_t now_ros_ns,
  const std::int64_t now_steady_ns) const
{
  if (!valid_stamp(
      sample.command.header.stamp, now_ros_ns, command_timeout_ns_, future_tolerance_ns_))
  {
    return false;
  }

  const std::int64_t receipt_age_ns = now_steady_ns - sample.received_steady_ns;
  return receipt_age_ns >= 0 && receipt_age_ns <= command_timeout_ns_;
}

}  // namespace buddy_safety
