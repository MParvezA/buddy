#include <cassert>
#include <string>

#include <rmw/types.h>
#include <ros_gz_bridge/bridge_config.hpp>

int main(int argc, char ** argv)
{
  assert(argc == 2);
  const auto configurations = ros_gz_bridge::readFromYamlFile(argv[1]);
  for (const auto & configuration : configurations) {
    if (configuration.ros_topic_name != "/odom/wheel") {
      continue;
    }
    const auto qos = configuration.PublisherQoS().get_rmw_qos_profile();
    assert(qos.history == RMW_QOS_POLICY_HISTORY_KEEP_LAST);
    assert(qos.depth == 10u);
    assert(qos.reliability == RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT);
    assert(qos.durability == RMW_QOS_POLICY_DURABILITY_VOLATILE);
    return 0;
  }
  return 1;
}
