// Copyright 2026 SyncRobot

#include <cmath>
#include <cstdint>
#include <limits>

#include "gtest/gtest.h"

#include "buddy_safety/command_arbiter_core.hpp"

namespace
{

constexpr std::int64_t kSecond = 1000000000LL;

geometry_msgs::msg::TwistStamped command(
  const std::int64_t stamp_ns,
  const double linear,
  const double angular)
{
  geometry_msgs::msg::TwistStamped value;
  value.header.stamp.sec = static_cast<std::int32_t>(stamp_ns / kSecond);
  value.header.stamp.nanosec = static_cast<std::uint32_t>(stamp_ns % kSecond);
  value.twist.linear.x = linear;
  value.twist.angular.z = angular;
  return value;
}

TEST(CommandArbiterCore, SelectsFrozenPriorityForConflictingFreshSources)
{
  buddy_safety::CommandArbiterCore arbiter(250000000, 100000000);
  const std::int64_t now = 10 * kSecond;

  EXPECT_TRUE(arbiter.submit(
      buddy_safety::MotionSource::kNavigation, command(now, 0.1, 0.0), now, now));
  EXPECT_TRUE(arbiter.submit(
      buddy_safety::MotionSource::kRecovery, command(now, 0.2, 0.0), now, now));
  EXPECT_TRUE(arbiter.submit(
      buddy_safety::MotionSource::kDocking, command(now, 0.3, 0.0), now, now));
  EXPECT_TRUE(arbiter.submit(
      buddy_safety::MotionSource::kTeleop, command(now, 0.4, 0.0), now, now));

  const auto selected = arbiter.select(now, now);
  ASSERT_TRUE(selected.has_source);
  EXPECT_EQ(selected.source, buddy_safety::MotionSource::kTeleop);
  EXPECT_DOUBLE_EQ(selected.command.twist.linear.x, 0.4);
  EXPECT_EQ(buddy_safety::CommandArbiterCore::priority(selected.source), 200);
}

TEST(CommandArbiterCore, FallsBackAsHigherPriorityCommandsBecomeStale)
{
  buddy_safety::CommandArbiterCore arbiter(250000000, 100000000);
  const std::int64_t now = 10 * kSecond;

  EXPECT_TRUE(arbiter.submit(
      buddy_safety::MotionSource::kNavigation,
      command(now + 100000000, 0.1, 0.0), now, now + 200000000));
  EXPECT_TRUE(arbiter.submit(
      buddy_safety::MotionSource::kTeleop, command(now, 0.4, 0.0), now, now));

  const auto selected = arbiter.select(now + 300000000, now + 300000000);
  ASSERT_TRUE(selected.has_source);
  EXPECT_EQ(selected.source, buddy_safety::MotionSource::kNavigation);

  const auto none = arbiter.select(now + 500000000, now + 500000000);
  EXPECT_FALSE(none.has_source);
}

TEST(CommandArbiterCore, RejectsNonFiniteAllowedVelocityAndInvalidTimestamps)
{
  buddy_safety::CommandArbiterCore arbiter(250000000, 100000000);
  const std::int64_t now = 10 * kSecond;

  auto nonfinite = command(now, std::numeric_limits<double>::infinity(), 0.0);
  EXPECT_FALSE(arbiter.submit(
      buddy_safety::MotionSource::kTeleop, nonfinite, now, now));
  EXPECT_FALSE(arbiter.submit(
      buddy_safety::MotionSource::kTeleop, command(0, 0.1, 0.0), now, now));
  EXPECT_FALSE(arbiter.submit(
      buddy_safety::MotionSource::kTeleop,
      command(now + 200000000, 0.1, 0.0), now, now));
  EXPECT_FALSE(arbiter.submit(
      buddy_safety::MotionSource::kTeleop,
      command(now - 300000000, 0.1, 0.0), now, now));
  EXPECT_FALSE(arbiter.select(now, now).has_source);
}

TEST(CommandArbiterCore, IgnoresDisallowedTwistAxes)
{
  buddy_safety::CommandArbiterCore arbiter(250000000, 100000000);
  const std::int64_t now = 10 * kSecond;
  auto input = command(now, 0.2, -0.3);
  input.twist.linear.y = std::numeric_limits<double>::quiet_NaN();
  input.twist.linear.z = 9.0;
  input.twist.angular.x = -4.0;
  input.twist.angular.y = 5.0;

  ASSERT_TRUE(arbiter.submit(
      buddy_safety::MotionSource::kDocking, input, now, now));
  const auto selected = arbiter.select(now, now);
  ASSERT_TRUE(selected.has_source);
  EXPECT_DOUBLE_EQ(selected.command.twist.linear.x, 0.2);
  EXPECT_DOUBLE_EQ(selected.command.twist.linear.y, 0.0);
  EXPECT_DOUBLE_EQ(selected.command.twist.linear.z, 0.0);
  EXPECT_DOUBLE_EQ(selected.command.twist.angular.x, 0.0);
  EXPECT_DOUBLE_EQ(selected.command.twist.angular.y, 0.0);
  EXPECT_DOUBLE_EQ(selected.command.twist.angular.z, -0.3);
}

}  // namespace
