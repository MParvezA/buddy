// Copyright 2026 SyncRobot

#include "buddy_safety/command_arbiter_node.hpp"

#include <chrono>
#include <functional>
#include <stdexcept>

namespace buddy_safety
{

namespace
{

constexpr char kNavigationTopic[] = "/buddy/motion/request/navigation";
constexpr char kTeleopTopic[] = "/buddy/motion/request/teleop";
constexpr char kDockingTopic[] = "/buddy/motion/request/docking";
constexpr char kRecoveryTopic[] = "/buddy/motion/request/recovery";
constexpr char kOutputTopic[] = "/buddy/motion/arbitrated_cmd_vel";

std::chrono::nanoseconds milliseconds_to_nanoseconds(const double milliseconds)
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::duration<double, std::milli>(milliseconds));
}

}  // namespace

CommandArbiterNode::CommandArbiterNode(const rclcpp::NodeOptions & options)
: Node("command_arbiter", "/buddy", options)
{
  const double timeout_ms = declare_parameter<double>("command_timeout_ms", 250.0);
  const double future_tolerance_ms = declare_parameter<double>("future_tolerance_ms", 100.0);
  const double publish_rate_hz = declare_parameter<double>("publish_rate_hz", 50.0);
  if (timeout_ms <= 0.0 || future_tolerance_ms < 0.0 || publish_rate_hz <= 0.0) {
    throw std::invalid_argument("arbiter timeout and rate parameters are invalid");
  }

  const std::string navigation_topic =
    declare_parameter<std::string>("navigation_topic", kNavigationTopic);
  const std::string teleop_topic =
    declare_parameter<std::string>("teleop_topic", kTeleopTopic);
  const std::string docking_topic =
    declare_parameter<std::string>("docking_topic", kDockingTopic);
  const std::string recovery_topic =
    declare_parameter<std::string>("recovery_topic", kRecoveryTopic);
  const std::string output_topic =
    declare_parameter<std::string>("output_topic", kOutputTopic);
  const std::string diagnostics_topic =
    declare_parameter<std::string>("diagnostics_topic", "/diagnostics");

  core_ = std::make_unique<CommandArbiterCore>(
    milliseconds_to_nanoseconds(timeout_ms).count(),
    milliseconds_to_nanoseconds(future_tolerance_ms).count());

  const auto motion_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().durability_volatile();
  output_publisher_ =
    create_publisher<geometry_msgs::msg::TwistStamped>(output_topic, motion_qos);
  diagnostics_publisher_ = create_publisher<diagnostic_msgs::msg::DiagnosticArray>(
    diagnostics_topic,
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile());
  navigation_subscription_ = create_subscription<geometry_msgs::msg::TwistStamped>(
    navigation_topic, motion_qos,
    [this](const geometry_msgs::msg::TwistStamped & command) {
      receive(MotionSource::kNavigation, command);
    });
  teleop_subscription_ = create_subscription<geometry_msgs::msg::TwistStamped>(
    teleop_topic, motion_qos,
    [this](const geometry_msgs::msg::TwistStamped & command) {
      receive(MotionSource::kTeleop, command);
    });
  docking_subscription_ = create_subscription<geometry_msgs::msg::TwistStamped>(
    docking_topic, motion_qos,
    [this](const geometry_msgs::msg::TwistStamped & command) {
      receive(MotionSource::kDocking, command);
    });
  recovery_subscription_ = create_subscription<geometry_msgs::msg::TwistStamped>(
    recovery_topic, motion_qos,
    [this](const geometry_msgs::msg::TwistStamped & command) {
      receive(MotionSource::kRecovery, command);
    });

  timer_ = create_wall_timer(
    std::chrono::duration<double>(1.0 / publish_rate_hz),
    std::bind(&CommandArbiterNode::publish_selected, this));
}

void CommandArbiterNode::receive(
  const MotionSource source,
  const geometry_msgs::msg::TwistStamped & command)
{
  std::string rejection_reason;
  bool accepted;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    accepted = core_->submit(
      source, command, now().nanoseconds(), steady_now_nanoseconds(), &rejection_reason);
  }
  if (!accepted) {
    RCLCPP_WARN(
      get_logger(), "Rejected %s motion request: %s",
      CommandArbiterCore::source_name(source), rejection_reason.c_str());
  }
}

void CommandArbiterNode::publish_selected()
{
  const rclcpp::Time output_time = now();
  SelectedCommand selected;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    selected = core_->select(output_time.nanoseconds(), steady_now_nanoseconds());
  }

  geometry_msgs::msg::TwistStamped output;
  if (selected.has_source) {
    output = selected.command;
  }
  output.header.stamp = output_time;
  output_publisher_->publish(output);

  diagnostic_msgs::msg::DiagnosticArray diagnostics;
  diagnostics.header.stamp = output_time;
  diagnostic_msgs::msg::DiagnosticStatus status;
  status.name = "buddy_command_arbiter";
  status.hardware_id = "software";
  status.level = diagnostic_msgs::msg::DiagnosticStatus::OK;
  status.message = selected.has_source ? "fresh motion request selected" :
    "safe zero output; no fresh motion request";
  diagnostic_msgs::msg::KeyValue source_value;
  source_value.key = "selected_source";
  source_value.value = selected.has_source ?
    CommandArbiterCore::source_name(selected.source) : "none";
  status.values.push_back(source_value);
  diagnostic_msgs::msg::KeyValue priority_value;
  priority_value.key = "priority";
  priority_value.value = selected.has_source ?
    std::to_string(CommandArbiterCore::priority(selected.source)) : "0";
  status.values.push_back(priority_value);
  diagnostics.status.push_back(status);
  diagnostics_publisher_->publish(diagnostics);
}

std::int64_t CommandArbiterNode::steady_now_nanoseconds()
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count();
}

}  // namespace buddy_safety
