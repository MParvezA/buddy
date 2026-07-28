#include <cassert>
#include <chrono>

#include <gz/msgs/twist.pb.h>

#include "buddy_gazebo/command_watchdog_state.hpp"

int main()
{
  using namespace std::chrono_literals;
  using State = buddy_gazebo::CommandWatchdogState;
  State watchdog(250ms);
  const auto start = State::Clock::time_point(1s);

  auto output = watchdog.Command(start);
  assert(output.linear().x() == 0.0);
  assert(output.angular().z() == 0.0);

  gz::msgs::Twist command;
  command.mutable_linear()->set_x(0.3);
  command.mutable_linear()->set_y(9.0);
  command.mutable_angular()->set_z(-0.4);
  watchdog.Receive(command, start);

  output = watchdog.Command(start + 249ms);
  assert(output.linear().x() == 0.3);
  assert(output.linear().y() == 0.0);
  assert(output.angular().z() == -0.4);

  output = watchdog.Command(start + 250ms);
  assert(output.linear().x() == 0.0);
  assert(output.angular().z() == 0.0);
  return 0;
}
