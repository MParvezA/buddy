// Copyright 2026 SyncRobot

#include <algorithm>
#include <atomic>
#include <chrono>
#include <future>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "gtest/gtest.h"

#include "buddy_interfaces/msg/emergency_stop_request.hpp"
#include "buddy_interfaces/msg/safety_state.hpp"
#include "buddy_interfaces/srv/reset_emergency_stop.hpp"
#include "diagnostic_msgs/msg/diagnostic_array.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "rclcpp/rclcpp.hpp"

#include "buddy_safety/command_arbiter_node.hpp"
#include "buddy_safety/safety_filter_node.hpp"

namespace
{

using namespace std::chrono_literals;

template<typename Predicate>
bool wait_until(Predicate predicate, const std::chrono::milliseconds timeout)
{
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  while (std::chrono::steady_clock::now() < deadline) {
    if (predicate()) {
      return true;
    }
    std::this_thread::sleep_for(10ms);
  }
  return predicate();
}

bool has_only_motion_publisher(
  const rclcpp::Node & probe,
  const std::string & node_name,
  const std::string & expected)
{
  std::vector<std::string> motion_topics;
  for (const auto & topic : probe.get_topic_names_and_types()) {
    if (topic.first.rfind("/buddy/motion/", 0) != 0) {
      continue;
    }
    for (const auto & publisher : probe.get_publishers_info_by_topic(topic.first)) {
      if (publisher.node_name() == node_name && publisher.node_namespace() == "/buddy") {
        motion_topics.push_back(topic.first);
      }
    }
  }
  std::sort(motion_topics.begin(), motion_topics.end());
  return motion_topics == std::vector<std::string>{expected};
}

TEST(MotionGraph, EnforcesPublisherBoundaryPriorityLatchAndResetService)
{
  rclcpp::init(0, nullptr);
  auto arbiter_options = rclcpp::NodeOptions().parameter_overrides(
    {rclcpp::Parameter("publish_rate_hz", 100.0)});
  auto safety_options = rclcpp::NodeOptions().parameter_overrides(
    {
      rclcpp::Parameter("publish_rate_hz", 100.0),
      rclcpp::Parameter("startup_inhibit_ms", 0.0),
      rclcpp::Parameter("require_scan", false),
      rclcpp::Parameter("max_linear_acceleration", 1000.0),
      rclcpp::Parameter("max_angular_acceleration", 1000.0),
    });
  auto arbiter = std::make_shared<buddy_safety::CommandArbiterNode>(arbiter_options);
  auto safety = std::make_shared<buddy_safety::SafetyFilterNode>(safety_options);
  auto probe = std::make_shared<rclcpp::Node>("motion_graph_probe");

  const auto motion_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().durability_volatile();
  const auto emergency_qos =
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();
  auto navigation_publisher =
    probe->create_publisher<geometry_msgs::msg::TwistStamped>(
    "/buddy/motion/request/navigation", motion_qos);
  auto teleop_publisher =
    probe->create_publisher<geometry_msgs::msg::TwistStamped>(
    "/buddy/motion/request/teleop", motion_qos);
  auto emergency_publisher =
    probe->create_publisher<buddy_interfaces::msg::EmergencyStopRequest>(
    "/buddy/safety/emergency_stop/request", emergency_qos);

  std::mutex observation_mutex;
  geometry_msgs::msg::TwistStamped arbitrated;
  geometry_msgs::msg::TwistStamped safe;
  buddy_interfaces::msg::SafetyState state;
  std::atomic<int> arbitrated_count{0};
  std::atomic<int> safe_count{0};
  std::atomic<int> state_count{0};
  std::atomic<bool> arbiter_diagnostic_seen{false};
  std::atomic<bool> safety_diagnostic_seen{false};
  auto arbitrated_subscription =
    probe->create_subscription<geometry_msgs::msg::TwistStamped>(
    "/buddy/motion/arbitrated_cmd_vel", motion_qos,
    [&](const geometry_msgs::msg::TwistStamped & message) {
      std::lock_guard<std::mutex> lock(observation_mutex);
      arbitrated = message;
      ++arbitrated_count;
    });
  auto safe_subscription = probe->create_subscription<geometry_msgs::msg::TwistStamped>(
    "/buddy/motion/safe_cmd_vel", motion_qos,
    [&](const geometry_msgs::msg::TwistStamped & message) {
      std::lock_guard<std::mutex> lock(observation_mutex);
      safe = message;
      ++safe_count;
    });
  auto state_subscription = probe->create_subscription<buddy_interfaces::msg::SafetyState>(
    "/buddy/safety/state",
    rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local(),
    [&](const buddy_interfaces::msg::SafetyState & message) {
      std::lock_guard<std::mutex> lock(observation_mutex);
      state = message;
      ++state_count;
    });
  auto diagnostics_subscription =
    probe->create_subscription<diagnostic_msgs::msg::DiagnosticArray>(
    "/diagnostics",
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile(),
    [&](const diagnostic_msgs::msg::DiagnosticArray & message) {
      for (const auto & status : message.status) {
        if (status.name == "buddy_command_arbiter") {
          arbiter_diagnostic_seen = true;
        }
        if (status.name == "buddy_safety_filter") {
          safety_diagnostic_seen = true;
        }
      }
    });
  auto reset_client =
    probe->create_client<buddy_interfaces::srv::ResetEmergencyStop>(
    "/buddy/safety/emergency_stop/reset");

  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(arbiter);
  executor.add_node(safety);
  executor.add_node(probe);
  std::thread spin_thread([&executor]() {executor.spin();});

  ASSERT_TRUE(wait_until(
      [&]() {
        return navigation_publisher->get_subscription_count() == 1 &&
               teleop_publisher->get_subscription_count() == 1 &&
               emergency_publisher->get_subscription_count() == 1 &&
               reset_client->service_is_ready();
      }, 2s));
  EXPECT_TRUE(wait_until(
      [&]() {return arbiter_diagnostic_seen && safety_diagnostic_seen;}, 2s));

  EXPECT_TRUE(has_only_motion_publisher(
      *probe, "command_arbiter",
      "/buddy/motion/arbitrated_cmd_vel"));
  EXPECT_TRUE(has_only_motion_publisher(
      *probe, "safety_filter",
      "/buddy/motion/safe_cmd_vel"));

  geometry_msgs::msg::TwistStamped navigation;
  navigation.header.stamp = probe->now();
  navigation.twist.linear.x = 0.1;
  geometry_msgs::msg::TwistStamped teleop = navigation;
  teleop.twist.linear.x = 0.4;
  navigation_publisher->publish(navigation);
  teleop_publisher->publish(teleop);

  ASSERT_TRUE(wait_until(
      [&]() {
        std::lock_guard<std::mutex> lock(observation_mutex);
        return arbitrated_count > 0 && arbitrated.twist.linear.x == 0.4 &&
               safe_count > 0 && safe.twist.linear.x == 0.4;
      }, 2s));

  buddy_interfaces::msg::EmergencyStopRequest emergency;
  emergency.header.stamp = probe->now();
  emergency.source = "component_test";
  emergency.reason_code =
    buddy_interfaces::msg::EmergencyStopRequest::REASON_OPERATOR;
  emergency.reason = "test stop";
  emergency_publisher->publish(emergency);

  ASSERT_TRUE(wait_until(
      [&]() {
        std::lock_guard<std::mutex> lock(observation_mutex);
        return state_count > 0 && state.emergency_stop_latched &&
               state.state == buddy_interfaces::msg::SafetyState::STATE_EMERGENCY_STOPPED &&
               safe.twist.linear.x == 0.0 && safe.twist.angular.z == 0.0;
      }, 2s));

  auto rejected_request =
    std::make_shared<buddy_interfaces::srv::ResetEmergencyStop::Request>();
  rejected_request->source = "operator";
  rejected_request->operator_acknowledged = false;
  auto rejected_future = reset_client->async_send_request(rejected_request);
  ASSERT_EQ(rejected_future.wait_for(2s), std::future_status::ready);
  EXPECT_FALSE(rejected_future.get()->success);

  auto accepted_request =
    std::make_shared<buddy_interfaces::srv::ResetEmergencyStop::Request>();
  accepted_request->source = "operator";
  accepted_request->operator_acknowledged = true;
  auto accepted_future = reset_client->async_send_request(accepted_request);
  ASSERT_EQ(accepted_future.wait_for(2s), std::future_status::ready);
  EXPECT_TRUE(accepted_future.get()->success);

  const auto physical_set_result =
    safety->set_parameter(rclcpp::Parameter("physical_emergency_stop_active", true));
  ASSERT_TRUE(physical_set_result.successful);
  ASSERT_TRUE(wait_until(
      [&]() {
        std::lock_guard<std::mutex> lock(observation_mutex);
        return state.emergency_stop_latched &&
               state.state == buddy_interfaces::msg::SafetyState::STATE_EMERGENCY_STOPPED &&
               state.source == "physical_emergency_stop" &&
               safe.twist.linear.x == 0.0;
      }, 2s));

  auto active_physical_reset_request =
    std::make_shared<buddy_interfaces::srv::ResetEmergencyStop::Request>();
  active_physical_reset_request->source = "operator";
  active_physical_reset_request->operator_acknowledged = true;
  auto active_physical_reset_future =
    reset_client->async_send_request(active_physical_reset_request);
  ASSERT_EQ(active_physical_reset_future.wait_for(2s), std::future_status::ready);
  EXPECT_FALSE(active_physical_reset_future.get()->success);

  const auto physical_release_result =
    safety->set_parameter(rclcpp::Parameter("physical_emergency_stop_active", false));
  ASSERT_TRUE(physical_release_result.successful);
  std::this_thread::sleep_for(50ms);
  {
    std::lock_guard<std::mutex> lock(observation_mutex);
    EXPECT_TRUE(state.emergency_stop_latched);
    EXPECT_EQ(state.state, buddy_interfaces::msg::SafetyState::STATE_EMERGENCY_STOPPED);
  }

  auto physical_reset_request =
    std::make_shared<buddy_interfaces::srv::ResetEmergencyStop::Request>();
  physical_reset_request->source = "operator";
  physical_reset_request->operator_acknowledged = true;
  auto physical_reset_future = reset_client->async_send_request(physical_reset_request);
  ASSERT_EQ(physical_reset_future.wait_for(2s), std::future_status::ready);
  EXPECT_TRUE(physical_reset_future.get()->success);

  executor.cancel();
  spin_thread.join();
  rclcpp::shutdown();

  (void)arbitrated_subscription;
  (void)safe_subscription;
  (void)state_subscription;
  (void)diagnostics_subscription;
}

}  // namespace
