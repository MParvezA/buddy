from buddy_perception.readiness_core import SensorTracker


def test_fake_sensor_fixture_becomes_ready():
    tracker = SensorTracker()
    fixture = {
        'scan': 'lidar_link',
        'imu': 'imu_link',
        'image': 'camera_optical_frame',
        'camera_info': 'camera_optical_frame',
    }
    for sensor, frame in fixture.items():
        tracker.observe(sensor, frame, received_at=10.0)
    result = tracker.readiness(now=10.5, timeout=1.0)
    assert result.ready
    assert result.missing == ()
    assert result.stale == ()


def test_missing_stale_and_invalid_frame_are_reported():
    tracker = SensorTracker()
    tracker.observe('scan', 'lidar_link', received_at=1.0)
    tracker.observe('imu', '', received_at=2.0)
    result = tracker.readiness(now=3.0, timeout=1.5)
    assert result.ready is False
    assert result.missing == ('image', 'camera_info')
    assert result.stale == ('scan',)
    assert result.invalid_frames == ('imu',)
