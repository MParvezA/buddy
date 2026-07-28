// Copyright 2026 SyncRobot

#ifndef BUDDY_SAFETY__COMMAND_ARBITER_CORE_HPP_
#define BUDDY_SAFETY__COMMAND_ARBITER_CORE_HPP_

#include <array>
#include <cstdint>
#include <optional>
#include <string>

#include "geometry_msgs/msg/twist_stamped.hpp"

namespace buddy_safety
{

enum class MotionSource : std::size_t
{
  kNavigation = 0,
  kRecovery = 1,
  kDocking = 2,
  kTeleop = 3,
};

struct SelectedCommand
{
  bool has_source{false};
  MotionSource source{MotionSource::kNavigation};
  geometry_msgs::msg::TwistStamped command;
};

class CommandArbiterCore
{
public:
  CommandArbiterCore(std::int64_t command_timeout_ns, std::int64_t future_tolerance_ns);

  bool submit(
    MotionSource source,
    const geometry_msgs::msg::TwistStamped & command,
    std::int64_t now_ros_ns,
    std::int64_t now_steady_ns,
    std::string * rejection_reason = nullptr);

  SelectedCommand select(std::int64_t now_ros_ns, std::int64_t now_steady_ns) const;

  static int priority(MotionSource source);
  static const char * source_name(MotionSource source);
  static bool valid_stamp(
    const builtin_interfaces::msg::Time & stamp,
    std::int64_t now_ros_ns,
    std::int64_t maximum_age_ns,
    std::int64_t future_tolerance_ns);
  static std::int64_t stamp_to_nanoseconds(const builtin_interfaces::msg::Time & stamp);

private:
  struct Sample
  {
    geometry_msgs::msg::TwistStamped command;
    std::int64_t received_steady_ns{0};
  };

  bool fresh(
    const Sample & sample,
    std::int64_t now_ros_ns,
    std::int64_t now_steady_ns) const;

  std::int64_t command_timeout_ns_;
  std::int64_t future_tolerance_ns_;
  std::array<std::optional<Sample>, 4> samples_;
};

}  // namespace buddy_safety

#endif  // BUDDY_SAFETY__COMMAND_ARBITER_CORE_HPP_
