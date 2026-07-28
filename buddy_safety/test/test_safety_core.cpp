// Copyright 2026 SyncRobot

#include <cstdint>
#include <limits>
#include <string>

#include "gtest/gtest.h"

#include "buddy_safety/safety_core.hpp"

namespace
{

constexpr std::int64_t kSecond = 1000000000LL;

builtin_interfaces::msg::Time stamp(const std::int64_t nanoseconds)
{
  builtin_interfaces::msg::Time result;
  result.sec = static_cast<std::int32_t>(nanoseconds / kSecond);
  result.nanosec = static_cast<std::uint32_t>(nanoseconds % kSecond);
  return result;
}

geometry_msgs::msg::TwistStamped command(
  const std::int64_t stamp_ns,
  const double linear,
  const double angular)
{
  geometry_msgs::msg::TwistStamped result;
  result.header.stamp = stamp(stamp_ns);
  result.twist.linear.x = linear;
  result.twist.angular.z = angular;
  return result;
}

sensor_msgs::msg::LaserScan scan(
  const std::int64_t stamp_ns,
  const float front_range,
  const float rear_range = std::numeric_limits<float>::infinity(),
  const float side_range = std::numeric_limits<float>::infinity())
{
  sensor_msgs::msg::LaserScan result;
  result.header.stamp = stamp(stamp_ns);
  result.angle_min = -3.1415927F;
  result.angle_max = 3.1415927F;
  result.angle_increment = 0.5235988F;
  result.range_min = 0.05F;
  result.range_max = 10.0F;
  result.ranges.assign(13, std::numeric_limits<float>::infinity());
  result.ranges[0] = rear_range;
  result.ranges[3] = side_range;
  result.ranges[6] = front_range;
  return result;
}

buddy_safety::SafetyConfig permissive_config()
{
  buddy_safety::SafetyConfig config;
  config.require_scan = false;
  config.startup_inhibit_ns = 0;
  config.command_timeout_ns = 10 * kSecond;
  config.max_linear_acceleration = 100.0;
  config.max_angular_acceleration = 100.0;
  return config;
}

TEST(SafetyCore, AppliesVelocityAndAccelerationLimits)
{
  auto config = permissive_config();
  config.max_linear_velocity = 0.5;
  config.max_angular_velocity = 1.0;
  config.max_linear_acceleration = 0.5;
  config.max_angular_acceleration = 1.0;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now);

  ASSERT_TRUE(safety.submit_command(command(now, 2.0, -3.0), now, now));
  const auto first = safety.evaluate(now + 200000000, now + 200000000);
  EXPECT_NEAR(first.output.twist.linear.x, 0.1, 1e-9);
  EXPECT_NEAR(first.output.twist.angular.z, -0.2, 1e-9);
  EXPECT_EQ(first.state, buddy_interfaces::msg::SafetyState::STATE_LIMITED);

  const auto settled = safety.evaluate(now + 2 * kSecond, now + 2 * kSecond);
  EXPECT_DOUBLE_EQ(settled.output.twist.linear.x, 0.5);
  EXPECT_DOUBLE_EQ(settled.output.twist.angular.z, -1.0);
}

TEST(SafetyCore, StopsForStaleAndNonFiniteCommands)
{
  auto config = permissive_config();
  config.command_timeout_ns = 250000000;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now);

  auto invalid = command(now, std::numeric_limits<double>::quiet_NaN(), 0.0);
  EXPECT_FALSE(safety.submit_command(invalid, now, now));
  auto decision = safety.evaluate(now, now);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_COMMAND_TIMEOUT);

  ASSERT_TRUE(safety.submit_command(command(now, 0.3, 0.1), now, now));
  decision = safety.evaluate(now + 300000000, now + 300000000);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_DOUBLE_EQ(decision.output.twist.angular.z, 0.0);
  EXPECT_FALSE(decision.motion_permitted);
}

TEST(SafetyCore, StopsAndSlowsForFrontObstacle)
{
  auto config = permissive_config();
  config.require_scan = true;
  config.obstacle_stop_distance = 0.25;
  config.obstacle_slowdown_distance = 0.75;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now - kSecond);

  ASSERT_TRUE(safety.submit_command(command(now, 0.4, 0.4), now, now));
  ASSERT_TRUE(safety.submit_scan(scan(now, 0.5F), now, now));
  auto decision = safety.evaluate(now + 100000000, now + 100000000);
  EXPECT_NEAR(decision.output.twist.linear.x, 0.2, 1e-6);
  EXPECT_NEAR(decision.output.twist.angular.z, 0.2, 1e-6);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_LIMITED);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_COLLISION_RISK);

  ASSERT_TRUE(safety.submit_scan(scan(now + 100000000, 0.2F),
      now + 100000000, now + 100000000));
  decision = safety.evaluate(now + 200000000, now + 200000000);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_DOUBLE_EQ(decision.output.twist.angular.z, 0.0);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_SOFT_STOPPED);
}

TEST(SafetyCore, StopsAndSlowsReverseForRearObstacle)
{
  auto config = permissive_config();
  config.require_scan = true;
  config.obstacle_stop_distance = 0.25;
  config.obstacle_slowdown_distance = 0.75;
  config.obstacle_stop_all_motion = false;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now - kSecond);

  ASSERT_TRUE(safety.submit_command(command(now, -0.4, 0.0), now, now));
  ASSERT_TRUE(safety.submit_scan(
      scan(now, std::numeric_limits<float>::infinity(), 0.5F), now, now));
  auto decision = safety.evaluate(now + 100000000, now + 100000000);
  EXPECT_NEAR(decision.output.twist.linear.x, -0.2, 1e-6);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_LIMITED);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_COLLISION_RISK);

  ASSERT_TRUE(safety.submit_scan(
      scan(now + 100000000, std::numeric_limits<float>::infinity(), 0.2F),
      now + 100000000, now + 100000000));
  decision = safety.evaluate(now + 200000000, now + 200000000);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_SOFT_STOPPED);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_COLLISION_RISK);
}

TEST(SafetyCore, FrontObstaclePermitsStraightRetreatWhenStopAllMotionIsDisabled)
{
  auto config = permissive_config();
  config.require_scan = true;
  config.obstacle_stop_all_motion = false;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now - kSecond);

  ASSERT_TRUE(safety.submit_command(command(now, -0.4, 0.0), now, now));
  ASSERT_TRUE(safety.submit_scan(scan(now, 0.2F), now, now));
  const auto decision = safety.evaluate(now + 100000000, now + 100000000);

  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, -0.4);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_NORMAL);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_NONE);
}

TEST(SafetyCore, RotationStopsForCloseObstacleAnywhereAroundRobot)
{
  auto config = permissive_config();
  config.require_scan = true;
  config.obstacle_stop_all_motion = false;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now - kSecond);

  ASSERT_TRUE(safety.submit_command(command(now, 0.0, 0.6), now, now));
  ASSERT_TRUE(safety.submit_scan(
      scan(
        now, std::numeric_limits<float>::infinity(),
        std::numeric_limits<float>::infinity(), 0.2F),
      now, now));
  const auto decision = safety.evaluate(now + 100000000, now + 100000000);

  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_DOUBLE_EQ(decision.output.twist.angular.z, 0.0);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_SOFT_STOPPED);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_COLLISION_RISK);
}

TEST(SafetyCore, InvalidSideSectorMakesRequiredScanUnhealthyForRotation)
{
  auto config = permissive_config();
  config.require_scan = true;
  config.obstacle_stop_all_motion = false;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now - kSecond);

  ASSERT_TRUE(safety.submit_command(command(now, 0.0, 0.6), now, now));
  std::string reason;
  EXPECT_FALSE(safety.submit_scan(
      scan(
        now, std::numeric_limits<float>::infinity(),
        std::numeric_limits<float>::infinity(),
        std::numeric_limits<float>::quiet_NaN()),
      now, now, &reason));
  EXPECT_EQ(reason, "scan has incomplete valid all-around angular coverage");

  const auto decision = safety.evaluate(now + 100000000, now + 100000000);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_DOUBLE_EQ(decision.output.twist.angular.z, 0.0);
  EXPECT_FALSE(decision.motion_permitted);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_FAULT);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_SENSOR_UNHEALTHY);
}

TEST(SafetyCore, FullKnownClearAllAroundCoveragePermitsRotation)
{
  auto config = permissive_config();
  config.require_scan = true;
  config.obstacle_stop_all_motion = false;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now - kSecond);

  ASSERT_TRUE(safety.submit_command(command(now, 0.0, 0.6), now, now));
  ASSERT_TRUE(safety.submit_scan(
      scan(now, std::numeric_limits<float>::infinity()), now, now));

  const auto decision = safety.evaluate(now + 100000000, now + 100000000);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_DOUBLE_EQ(decision.output.twist.angular.z, 0.6);
  EXPECT_TRUE(decision.motion_permitted);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_NORMAL);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_NONE);
}

TEST(SafetyCore, RejectsMalformedOrInsufficientDirectionalScanCoverage)
{
  auto config = permissive_config();
  config.require_scan = true;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now - kSecond);
  ASSERT_TRUE(safety.submit_command(command(now, -0.3, 0.0), now, now));

  auto front_only = scan(now, 1.0F);
  front_only.angle_min = -1.0F;
  front_only.angle_max = 1.0F;
  front_only.angle_increment = 0.5F;
  front_only.ranges.assign(5, std::numeric_limits<float>::infinity());
  std::string reason;
  EXPECT_FALSE(safety.submit_scan(front_only, now, now, &reason));
  EXPECT_EQ(reason, "scan has insufficient valid front or rear arc coverage");

  auto malformed = scan(now, 1.0F);
  malformed.angle_max = 100.0F;
  EXPECT_FALSE(safety.submit_scan(malformed, now, now, &reason));
  EXPECT_EQ(reason, "scan angle bounds do not match its sample count");

  const auto decision = safety.evaluate(now + 100000000, now + 100000000);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_FAULT);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_SENSOR_UNHEALTHY);
}

TEST(SafetyCore, StartupAndUnhealthySensorAlwaysProduceSafeZero)
{
  buddy_safety::SafetyConfig config;
  config.startup_inhibit_ns = 500000000;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now);

  ASSERT_TRUE(safety.submit_command(command(now, 0.4, 0.0), now, now));
  auto decision = safety.evaluate(now + 100000000, now + 100000000);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_STARTUP_INHIBIT);

  decision = safety.evaluate(now + 600000000, now + 600000000);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_FAULT);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_SENSOR_UNHEALTHY);
}

TEST(SafetyCore, EmergencyStopLatchesAndResetRequiresEveryClearCondition)
{
  const auto config = permissive_config();
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now);
  buddy_interfaces::msg::EmergencyStopRequest request;
  request.source = "voice_stop";
  request.reason = "stop";
  request.reason_code =
    buddy_interfaces::msg::EmergencyStopRequest::REASON_VOICE_COMMAND;

  ASSERT_TRUE(safety.submit_command(command(now, 0.4, 0.0), now, now));
  safety.latch_emergency_stop(request);
  auto decision = safety.evaluate(now + 100000000, now + 100000000);
  EXPECT_TRUE(decision.emergency_stop_latched);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_EMERGENCY_STOPPED);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);

  std::string message;
  EXPECT_FALSE(safety.reset_emergency_stop(false, true, now, now, &message));
  EXPECT_TRUE(safety.emergency_stop_latched());
  EXPECT_FALSE(safety.reset_emergency_stop(true, false, now, now, &message));
  EXPECT_TRUE(safety.emergency_stop_latched());
  safety.set_physical_emergency_stop_active(true);
  EXPECT_FALSE(safety.reset_emergency_stop(true, true, now, now, &message));
  EXPECT_TRUE(safety.emergency_stop_latched());
  safety.set_physical_emergency_stop_active(false);
  EXPECT_TRUE(safety.reset_emergency_stop(true, true, now, now, &message));
  EXPECT_FALSE(safety.emergency_stop_latched());
}

TEST(SafetyCore, ResetRejectsUnhealthyRequiredSensor)
{
  auto config = permissive_config();
  config.require_scan = true;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now);
  buddy_interfaces::msg::EmergencyStopRequest request;
  safety.latch_emergency_stop(request);

  std::string message;
  EXPECT_FALSE(safety.reset_emergency_stop(true, true, now, now, &message));
  EXPECT_TRUE(safety.emergency_stop_latched());
  ASSERT_TRUE(safety.submit_scan(
      scan(now, std::numeric_limits<float>::infinity()), now, now));
  EXPECT_TRUE(safety.reset_emergency_stop(true, true, now, now, &message));
}

TEST(SafetyCore, PhysicalInputLatchesUntilExplicitResetAfterRelease)
{
  const auto config = permissive_config();
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now);
  ASSERT_TRUE(safety.submit_command(command(now, 0.4, 0.0), now, now));

  safety.set_physical_emergency_stop_active(true);
  auto decision = safety.evaluate(now + 100000000, now + 100000000);
  EXPECT_TRUE(decision.emergency_stop_latched);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_EMERGENCY_STOPPED);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);

  std::string message;
  EXPECT_FALSE(safety.reset_emergency_stop(
      true, true, now + 100000000, now + 100000000, &message));
  safety.set_physical_emergency_stop_active(false);
  decision = safety.evaluate(now + 200000000, now + 200000000);
  EXPECT_TRUE(decision.emergency_stop_latched);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_EMERGENCY_STOPPED);
  EXPECT_TRUE(safety.reset_emergency_stop(
      true, true, now + 200000000, now + 200000000, &message));
  EXPECT_FALSE(safety.emergency_stop_latched());
}

TEST(SafetyCore, ControllerWatchdogStopsForMissingFaultedAndStaleHealth)
{
  auto config = permissive_config();
  config.require_controller_diagnostics = true;
  config.controller_diagnostics_timeout_ns = 500000000;
  const std::int64_t now = 10 * kSecond;
  buddy_safety::SafetyCore safety(config, now);
  ASSERT_TRUE(safety.submit_command(command(now, 0.3, 0.0), now, now));

  auto decision = safety.evaluate(now + 100000000, now + 100000000);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_FAULT);
  EXPECT_EQ(decision.reason_code, buddy_interfaces::msg::SafetyState::REASON_CONTROLLER_FAULT);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);

  safety.set_controller_health(true, now + 100000000);
  decision = safety.evaluate(now + 200000000, now + 200000000);
  EXPECT_TRUE(decision.motion_permitted);
  EXPECT_GT(decision.output.twist.linear.x, 0.0);

  decision = safety.evaluate(now + 700000000, now + 700000000);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_FAULT);
  EXPECT_DOUBLE_EQ(decision.output.twist.linear.x, 0.0);

  safety.set_controller_health(false, now + 700000000);
  decision = safety.evaluate(now + 800000000, now + 800000000);
  EXPECT_EQ(decision.state, buddy_interfaces::msg::SafetyState::STATE_FAULT);
}

}  // namespace
