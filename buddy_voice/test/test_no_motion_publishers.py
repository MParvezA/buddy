"""Guard the voice package boundary against accidental motion control imports."""

from pathlib import Path


def test_voice_package_has_no_motion_interfaces_or_publishers() -> None:
    """Voice only produces voice/safety interfaces, never wheel or velocity output."""
    package_directory = Path(__file__).parents[1] / 'buddy_voice'
    source = '\n'.join(path.read_text() for path in package_directory.glob('*.py'))

    forbidden = (
        'geometry_msgs',
        'Twist',
        'cmd_vel',
        'arbitrated_cmd_vel',
        'safe_cmd_vel',
        'NavigateToPose',
        'nav2',
    )
    assert not [term for term in forbidden if term in source]
