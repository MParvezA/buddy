// Copyright 2026 SyncRobot

#include <memory>

#include "rclcpp/rclcpp.hpp"

#include "buddy_safety/command_arbiter_node.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<buddy_safety::CommandArbiterNode>());
  rclcpp::shutdown();
  return 0;
}
