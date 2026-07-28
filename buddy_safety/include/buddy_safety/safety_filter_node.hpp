// Copyright 2026 SyncRobot

#ifndef BUDDY_SAFETY__SAFETY_FILTER_NODE_HPP_
#define BUDDY_SAFETY__SAFETY_FILTER_NODE_HPP_

#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "buddy_interfaces/msg/emergency_stop_request.hpp"
#include "buddy_interfaces/msg/safety_state.hpp"
#include "buddy_interfaces/srv/reset_emergency_stop.hpp"
#include "diagnostic_msgs/msg/diagnostic_array.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "rcl_interfaces/msg/set_parameters_result.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"

#include "buddy_safety/safety_core.hpp"

namespace buddy_safety
{

class SafetyFilterNode : public rclcpp::Node
{
public:
  explicit SafetyFilterNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  void receive_command(const geometry_msgs::msg::TwistStamped & command);
  void receive_scan(const sensor_msgs::msg::LaserScan & scan);
  void receive_emergency_stop(
    const buddy_interfaces::msg::EmergencyStopRequest & request);
  void receive_diagnostics(const diagnostic_msgs::msg::DiagnosticArray & diagnostics);
  void reset_emergency_stop(
    const std::shared_ptr<buddy_interfaces::srv::ResetEmergencyStop::Request> request,
    std::shared_ptr<buddy_interfaces::srv::ResetEmergencyStop::Response> response);
  void publish_filtered();
  void publish_decision(const SafetyDecision & decision);
  rcl_interfaces::msg::SetParametersResult parameters_changed(
    const std::vector<rclcpp::Parameter> & parameters);
  buddy_interfaces::msg::SafetyState make_state(const SafetyDecision & decision) const;
  bool reset_source_allowed(const std::string & source) const;
  static std::int64_t steady_now_nanoseconds();

  std::mutex mutex_;
  std::unique_ptr<SafetyCore> core_;
  std::vector<std::string> allowed_reset_sources_;
  std::string controller_diagnostic_name_;

  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr output_publisher_;
  rclcpp::Publisher<buddy_interfaces::msg::SafetyState>::SharedPtr state_publisher_;
  rclcpp::Publisher<diagnostic_msgs::msg::DiagnosticArray>::SharedPtr
    diagnostics_publisher_;
  rclcpp::Subscription<geometry_msgs::msg::TwistStamped>::SharedPtr command_subscription_;
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_subscription_;
  rclcpp::Subscription<buddy_interfaces::msg::EmergencyStopRequest>::SharedPtr
    emergency_stop_subscription_;
  rclcpp::Subscription<diagnostic_msgs::msg::DiagnosticArray>::SharedPtr
    diagnostics_subscription_;
  rclcpp::Service<buddy_interfaces::srv::ResetEmergencyStop>::SharedPtr reset_service_;
  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::node_interfaces::OnSetParametersCallbackHandle::SharedPtr
    parameter_callback_handle_;
};

}  // namespace buddy_safety

#endif  // BUDDY_SAFETY__SAFETY_FILTER_NODE_HPP_
