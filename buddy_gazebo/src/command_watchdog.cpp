#include <chrono>
#include <memory>
#include <string>

#include <gz/common/Console.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/transport/Node.hh>

#include "buddy_gazebo/command_watchdog_state.hpp"

namespace buddy_gazebo
{

class CommandWatchdog final :
  public gz::sim::System,
  public gz::sim::ISystemConfigure,
  public gz::sim::ISystemPreUpdate
{
public:
  void Configure(
    const gz::sim::Entity &,
    const std::shared_ptr<const sdf::Element> & sdf,
    gz::sim::EntityComponentManager &,
    gz::sim::EventManager &) override
  {
    input_topic_ = sdf->Get<std::string>(
      "input_topic", "/model/buddy/watchdog/input").first;
    output_topic_ = sdf->Get<std::string>(
      "output_topic", "/model/buddy/watchdog/output").first;
    const double timeout = sdf->Get<double>("timeout", 0.25).first;
    const double publish_rate = sdf->Get<double>("publish_rate", 50.0).first;
    if (input_topic_ == output_topic_ || timeout <= 0.0 || publish_rate <= 0.0) {
      gzerr << "Buddy command watchdog has invalid configuration" << std::endl;
      return;
    }

    state_ = std::make_unique<CommandWatchdogState>(
      std::chrono::duration<double>(timeout));
    publish_period_ = std::chrono::duration_cast<Clock::duration>(
      std::chrono::duration<double>(1.0 / publish_rate));
    publisher_ = node_.Advertise<gz::msgs::Twist>(output_topic_);
    configured_ = node_.Subscribe(
      input_topic_, &CommandWatchdog::OnCommand, this);
    if (!configured_) {
      gzerr << "Buddy command watchdog failed to subscribe to ["
            << input_topic_ << "]" << std::endl;
    }
  }

  void PreUpdate(
    const gz::sim::UpdateInfo &,
    gz::sim::EntityComponentManager &) override
  {
    if (!configured_) {
      return;
    }
    const auto now = Clock::now();
    if (published_ && now - last_publish_ < publish_period_) {
      return;
    }
    publisher_.Publish(state_->Command(now));
    last_publish_ = now;
    published_ = true;
  }

private:
  using Clock = CommandWatchdogState::Clock;

  void OnCommand(const gz::msgs::Twist & command)
  {
    state_->Receive(command, Clock::now());
  }

  gz::transport::Node node_;
  gz::transport::Node::Publisher publisher_;
  std::unique_ptr<CommandWatchdogState> state_;
  std::string input_topic_;
  std::string output_topic_;
  Clock::duration publish_period_{};
  Clock::time_point last_publish_;
  bool published_{false};
  bool configured_{false};
};

}  // namespace buddy_gazebo

GZ_ADD_PLUGIN(
  buddy_gazebo::CommandWatchdog,
  gz::sim::System,
  gz::sim::ISystemConfigure,
  gz::sim::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(
  buddy_gazebo::CommandWatchdog,
  "buddy_gazebo::CommandWatchdog")
