from pathlib import Path


WORKSPACE = Path(__file__).parents[2]
ENTRY_POINTS = (
    WORKSPACE / 'buddy_navigation' / 'buddy_navigation'
    / 'named_navigation_adapter.py',
    WORKSPACE / 'buddy_navigation' / 'buddy_navigation' / 'velocity_boundary.py',
    WORKSPACE / 'buddy_perception' / 'buddy_perception' / 'sensor_readiness.py',
    WORKSPACE / 'buddy_world_model' / 'buddy_world_model' / 'world_model_node.py',
)


def test_owned_rclpy_entry_points_handle_external_shutdown_narrowly():
    for path in ENTRY_POINTS:
        source = path.read_text()
        assert 'ExternalShutdownException' in source, path
        assert 'except (KeyboardInterrupt, ExternalShutdownException):' in source, path
        assert source.count(
            'except (KeyboardInterrupt, ExternalShutdownException):'
        ) >= 2, path
        assert 'node.destroy_node()' in source, path
        assert 'if rclpy.ok():' in source, path
        assert 'except Exception' not in source, path
