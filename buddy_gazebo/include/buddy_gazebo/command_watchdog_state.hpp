#ifndef BUDDY_GAZEBO__COMMAND_WATCHDOG_STATE_HPP_
#define BUDDY_GAZEBO__COMMAND_WATCHDOG_STATE_HPP_

#include <chrono>
#include <mutex>

#include <gz/msgs/twist.pb.h>

namespace buddy_gazebo
{

class CommandWatchdogState
{
public:
  using Clock = std::chrono::steady_clock;

  explicit CommandWatchdogState(const std::chrono::duration<double> timeout)
  : timeout_(timeout)
  {
  }

  void Receive(const gz::msgs::Twist & command, const Clock::time_point now)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    command_ = command;
    last_receive_ = now;
    received_ = true;
  }

  gz::msgs::Twist Command(const Clock::time_point now) const
  {
    std::lock_guard<std::mutex> lock(mutex_);
    gz::msgs::Twist output;
    if (!received_ || now - last_receive_ >= timeout_) {
      return output;
    }
    output.mutable_linear()->set_x(command_.linear().x());
    output.mutable_angular()->set_z(command_.angular().z());
    return output;
  }

private:
  const std::chrono::duration<double> timeout_;
  mutable std::mutex mutex_;
  gz::msgs::Twist command_;
  Clock::time_point last_receive_;
  bool received_{false};
};

}  // namespace buddy_gazebo

#endif  // BUDDY_GAZEBO__COMMAND_WATCHDOG_STATE_HPP_
