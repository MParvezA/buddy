from buddy_perception.sensor_readiness import sensor_qos
from rclpy.qos import DurabilityPolicy, HistoryPolicy, ReliabilityPolicy


def test_raw_sensor_qos_is_exactly_frozen_profile():
    qos = sensor_qos()
    assert qos.history == HistoryPolicy.KEEP_LAST
    assert qos.depth == 5
    assert qos.reliability == ReliabilityPolicy.BEST_EFFORT
    assert qos.durability == DurabilityPolicy.VOLATILE
