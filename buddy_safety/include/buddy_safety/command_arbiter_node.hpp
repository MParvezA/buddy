// Copyright 2026 SyncRobot

#ifndef BUDDY_SAFETY__COMMAND_ARBITER_NODE_HPP_
#define BUDDY_SAFETY__COMMAND_ARBITER_NODE_HPP_

#include <memory>
#include <mutex>
#include <string>

#include "diagnostic_msgs/msg/diagnostic_array.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "rclcpp/rclcpp.hpp"

#include "buddy_safety/command_arbiter_core.hpp"

namespace buddy_safety
{

class CommandArbiterNode : public rclcpp::Node
{
public:
  explicit CommandArbiterNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  void receive(MotionSource source, const geometry_msgs::msg::TwistStamped & command);
  void publish_selected();
  static std::int64_t steady_now_nanoseconds();

  std::mutex mutex_;
  std::unique_ptr<CommandArbiterCore> core_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr output_publisher_;
  rclcpp::Publisher<diagnostic_msgs::msg::DiagnosticArray>::SharedPtr
    diagnostics_publisher_;
  rclcpp::Subscription<geometry_msgs::msg::TwistStamped>::SharedPtr navigation_subscription_;
  rclcpp::Subscription<geometry_msgs::msg::TwistStamped>::SharedPtr teleop_subscription_;
  rclcpp::Subscription<geometry_msgs::msg::TwistStamped>::SharedPtr docking_subscription_;
  rclcpp::Subscription<geometry_msgs::msg::TwistStamped>::SharedPtr recovery_subscription_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace buddy_safety

#endif  // BUDDY_SAFETY__COMMAND_ARBITER_NODE_HPP_
