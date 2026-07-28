// Copyright 2026 SyncRobot

#include <memory>

#include "rclcpp/rclcpp.hpp"

#include "buddy_safety/safety_filter_node.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<buddy_safety::SafetyFilterNode>());
  rclcpp::shutdown();
  return 0;
}
