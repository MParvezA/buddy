// Copyright 2026 SyncRobot

#include "buddy_safety/safety_filter_node.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <functional>
#include <stdexcept>

namespace buddy_safety
{

namespace
{

constexpr char kCommandTopic[] = "/buddy/motion/arbitrated_cmd_vel";
constexpr char kOutputTopic[] = "/buddy/motion/safe_cmd_vel";
constexpr char kEmergencyStopTopic[] = "/buddy/safety/emergency_stop/request";
constexpr char kEmergencyStopResetService[] = "/buddy/safety/emergency_stop/reset";
constexpr char kSafetyStateTopic[] = "/buddy/safety/state";
constexpr char kScanTopic[] = "/scan";
constexpr char kDiagnosticsTopic[] = "/diagnostics";
constexpr double kDegreesToRadians = 0.017453292519943295;

std::int64_t milliseconds_to_nanoseconds(const double milliseconds)
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::duration<double, std::milli>(milliseconds)).count();
}

}  // namespace

SafetyFilterNode::SafetyFilterNode(const rclcpp::NodeOptions & options)
: Node("safety_filter", "/buddy", options)
{
  SafetyConfig config;
  config.max_linear_velocity =
    declare_parameter<double>("max_linear_velocity", config.max_linear_velocity);
  config.max_angular_velocity =
    declare_parameter<double>("max_angular_velocity", config.max_angular_velocity);
  config.max_linear_acceleration =
    declare_parameter<double>("max_linear_acceleration", config.max_linear_acceleration);
  config.max_angular_acceleration =
    declare_parameter<double>("max_angular_acceleration", config.max_angular_acceleration);
  config.obstacle_stop_distance =
    declare_parameter<double>("obstacle_stop_distance", config.obstacle_stop_distance);
  config.obstacle_slowdown_distance =
    declare_parameter<double>(
    "obstacle_slowdown_distance", config.obstacle_slowdown_distance);
  config.obstacle_front_arc_radians =
    declare_parameter<double>("obstacle_front_arc_degrees", 60.0) * kDegreesToRadians;
  config.obstacle_stop_all_motion =
    declare_parameter<bool>("obstacle_stop_all_motion", config.obstacle_stop_all_motion);
  config.obstacle_scale_angular =
    declare_parameter<bool>("obstacle_scale_angular", config.obstacle_scale_angular);
  config.require_scan = declare_parameter<bool>("require_scan", config.require_scan);
  config.require_controller_diagnostics = declare_parameter<bool>(
    "require_controller_diagnostics", config.require_controller_diagnostics);
  config.command_timeout_ns = milliseconds_to_nanoseconds(
    declare_parameter<double>("command_timeout_ms", 250.0));
  config.scan_timeout_ns = milliseconds_to_nanoseconds(
    declare_parameter<double>("scan_timeout_ms", 500.0));
  config.controller_diagnostics_timeout_ns = milliseconds_to_nanoseconds(
    declare_parameter<double>("controller_diagnostics_timeout_ms", 500.0));
  config.future_tolerance_ns = milliseconds_to_nanoseconds(
    declare_parameter<double>("future_tolerance_ms", 100.0));
  config.startup_inhibit_ns = milliseconds_to_nanoseconds(
    declare_parameter<double>("startup_inhibit_ms", 500.0));

  const double publish_rate_hz = declare_parameter<double>("publish_rate_hz", 50.0);
  if (!std::isfinite(publish_rate_hz) || publish_rate_hz <= 0.0) {
    throw std::invalid_argument("publish_rate_hz must be finite and positive");
  }

  allowed_reset_sources_ = declare_parameter<std::vector<std::string>>(
    "allowed_reset_sources", {"operator", "safety_panel", "physical_panel"});
  controller_diagnostic_name_ = declare_parameter<std::string>(
    "controller_diagnostic_name", "buddy_base_controller");
  declare_parameter<bool>("physical_emergency_stop_active", false);

  const std::string command_topic =
    declare_parameter<std::string>("command_topic", kCommandTopic);
  const std::string output_topic =
    declare_parameter<std::string>("output_topic", kOutputTopic);
  const std::string emergency_stop_topic =
    declare_parameter<std::string>("emergency_stop_topic", kEmergencyStopTopic);
  const std::string reset_service =
    declare_parameter<std::string>("reset_service", kEmergencyStopResetService);
  const std::string state_topic =
    declare_parameter<std::string>("state_topic", kSafetyStateTopic);
  const std::string scan_topic = declare_parameter<std::string>("scan_topic", kScanTopic);
  const std::string diagnostics_topic =
    declare_parameter<std::string>("diagnostics_topic", kDiagnosticsTopic);

  core_ = std::make_unique<SafetyCore>(config, steady_now_nanoseconds());

  const auto motion_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().durability_volatile();
  const auto emergency_qos =
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();
  const auto state_qos =
    rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();

  output_publisher_ =
    create_publisher<geometry_msgs::msg::TwistStamped>(output_topic, motion_qos);
  state_publisher_ =
    create_publisher<buddy_interfaces::msg::SafetyState>(state_topic, state_qos);
  diagnostics_publisher_ = create_publisher<diagnostic_msgs::msg::DiagnosticArray>(
    diagnostics_topic,
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile());
  command_subscription_ = create_subscription<geometry_msgs::msg::TwistStamped>(
    command_topic, motion_qos,
    std::bind(&SafetyFilterNode::receive_command, this, std::placeholders::_1));
  scan_subscription_ = create_subscription<sensor_msgs::msg::LaserScan>(
    scan_topic, rclcpp::SensorDataQoS(),
    std::bind(&SafetyFilterNode::receive_scan, this, std::placeholders::_1));
  emergency_stop_subscription_ =
    create_subscription<buddy_interfaces::msg::EmergencyStopRequest>(
    emergency_stop_topic, emergency_qos,
    std::bind(&SafetyFilterNode::receive_emergency_stop, this, std::placeholders::_1));
  diagnostics_subscription_ = create_subscription<diagnostic_msgs::msg::DiagnosticArray>(
    diagnostics_topic,
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile(),
    std::bind(&SafetyFilterNode::receive_diagnostics, this, std::placeholders::_1));
  reset_service_ = create_service<buddy_interfaces::srv::ResetEmergencyStop>(
    reset_service,
    std::bind(
      &SafetyFilterNode::reset_emergency_stop, this,
      std::placeholders::_1, std::placeholders::_2));

  timer_ = create_wall_timer(
    std::chrono::duration<double>(1.0 / publish_rate_hz),
    std::bind(&SafetyFilterNode::publish_filtered, this));

  core_->set_physical_emergency_stop_active(
    get_parameter("physical_emergency_stop_active").as_bool());
  parameter_callback_handle_ = add_on_set_parameters_callback(
    std::bind(&SafetyFilterNode::parameters_changed, this, std::placeholders::_1));
  publish_filtered();
}

void SafetyFilterNode::receive_command(const geometry_msgs::msg::TwistStamped & command)
{
  std::string rejection_reason;
  bool accepted;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    accepted = core_->submit_command(
      command, now().nanoseconds(), steady_now_nanoseconds(), &rejection_reason);
  }
  if (!accepted) {
    RCLCPP_WARN(get_logger(), "Rejected arbitrated command: %s", rejection_reason.c_str());
  }
}

void SafetyFilterNode::receive_scan(const sensor_msgs::msg::LaserScan & scan)
{
  std::string rejection_reason;
  bool accepted;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    accepted = core_->submit_scan(
      scan, now().nanoseconds(), steady_now_nanoseconds(), &rejection_reason);
  }
  if (!accepted) {
    RCLCPP_WARN(get_logger(), "Rejected safety scan: %s", rejection_reason.c_str());
  }
}

void SafetyFilterNode::receive_emergency_stop(
  const buddy_interfaces::msg::EmergencyStopRequest & request)
{
  SafetyDecision decision;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    core_->latch_emergency_stop(request);
    decision = core_->evaluate(now().nanoseconds(), steady_now_nanoseconds());
  }
  publish_decision(decision);
}

void SafetyFilterNode::receive_diagnostics(
  const diagnostic_msgs::msg::DiagnosticArray & diagnostics)
{
  const auto status = std::find_if(
    diagnostics.status.begin(), diagnostics.status.end(),
    [this](const diagnostic_msgs::msg::DiagnosticStatus & value) {
      return value.name == controller_diagnostic_name_;
    });
  if (status == diagnostics.status.end()) {
    return;
  }

  std::lock_guard<std::mutex> lock(mutex_);
  core_->set_controller_health(
    status->level == diagnostic_msgs::msg::DiagnosticStatus::OK,
    steady_now_nanoseconds());
}

void SafetyFilterNode::reset_emergency_stop(
  const std::shared_ptr<buddy_interfaces::srv::ResetEmergencyStop::Request> request,
  std::shared_ptr<buddy_interfaces::srv::ResetEmergencyStop::Response> response)
{
  SafetyDecision decision;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    response->success = core_->reset_emergency_stop(
      request->operator_acknowledged,
      reset_source_allowed(request->source),
      now().nanoseconds(), steady_now_nanoseconds(), &response->message);
    decision = core_->evaluate(now().nanoseconds(), steady_now_nanoseconds());
  }
  response->state = make_state(decision);
  publish_decision(decision);
}

void SafetyFilterNode::publish_filtered()
{
  SafetyDecision decision;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    decision = core_->evaluate(now().nanoseconds(), steady_now_nanoseconds());
  }
  publish_decision(decision);
}

void SafetyFilterNode::publish_decision(const SafetyDecision & decision)
{
  output_publisher_->publish(decision.output);
  state_publisher_->publish(make_state(decision));

  diagnostic_msgs::msg::DiagnosticArray diagnostics;
  diagnostics.header.stamp = decision.output.header.stamp;
  diagnostic_msgs::msg::DiagnosticStatus status;
  status.name = "buddy_safety_filter";
  status.hardware_id = "software";
  status.level = diagnostic_msgs::msg::DiagnosticStatus::OK;
  if (decision.state == buddy_interfaces::msg::SafetyState::STATE_LIMITED ||
    decision.state == buddy_interfaces::msg::SafetyState::STATE_SOFT_STOPPED)
  {
    status.level = diagnostic_msgs::msg::DiagnosticStatus::WARN;
  }
  if (decision.state == buddy_interfaces::msg::SafetyState::STATE_FAULT ||
    decision.state == buddy_interfaces::msg::SafetyState::STATE_EMERGENCY_STOPPED)
  {
    status.level = diagnostic_msgs::msg::DiagnosticStatus::ERROR;
  }
  status.message = decision.message;
  diagnostic_msgs::msg::KeyValue state_value;
  state_value.key = "state";
  state_value.value = std::to_string(decision.state);
  status.values.push_back(state_value);
  diagnostic_msgs::msg::KeyValue reason_value;
  reason_value.key = "reason_code";
  reason_value.value = std::to_string(decision.reason_code);
  status.values.push_back(reason_value);
  diagnostic_msgs::msg::KeyValue latch_value;
  latch_value.key = "emergency_stop_latched";
  latch_value.value = decision.emergency_stop_latched ? "true" : "false";
  status.values.push_back(latch_value);
  diagnostics.status.push_back(status);
  diagnostics_publisher_->publish(diagnostics);
}

rcl_interfaces::msg::SetParametersResult SafetyFilterNode::parameters_changed(
  const std::vector<rclcpp::Parameter> & parameters)
{
  rcl_interfaces::msg::SetParametersResult result;
  result.successful = true;
  for (const auto & parameter : parameters) {
    if (parameter.get_name() != "physical_emergency_stop_active") {
      continue;
    }
    if (parameter.get_type() != rclcpp::ParameterType::PARAMETER_BOOL) {
      result.successful = false;
      result.reason = "physical_emergency_stop_active must be a boolean";
      return result;
    }

    SafetyDecision decision;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      core_->set_physical_emergency_stop_active(parameter.as_bool());
      decision = core_->evaluate(now().nanoseconds(), steady_now_nanoseconds());
    }
    publish_decision(decision);
  }
  return result;
}

buddy_interfaces::msg::SafetyState SafetyFilterNode::make_state(
  const SafetyDecision & decision) const
{
  buddy_interfaces::msg::SafetyState state;
  state.header.stamp = decision.output.header.stamp;
  state.state = decision.state;
  state.reason_code = decision.reason_code;
  state.motion_permitted = decision.motion_permitted;
  state.emergency_stop_latched = decision.emergency_stop_latched;
  state.source = decision.source;
  state.message = decision.message;
  return state;
}

bool SafetyFilterNode::reset_source_allowed(const std::string & source) const
{
  return std::find(
    allowed_reset_sources_.begin(), allowed_reset_sources_.end(), source) !=
         allowed_reset_sources_.end();
}

std::int64_t SafetyFilterNode::steady_now_nanoseconds()
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count();
}

}  // namespace buddy_safety
