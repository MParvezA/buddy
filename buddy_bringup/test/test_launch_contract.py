"""Static checks for root-owned full-system composition."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAUNCH = ROOT / 'buddy_bringup' / 'launch' / 'simulation.launch.py'


def test_full_launch_composes_every_layer_and_sim_time():
    """The production simulation launch includes every bounded layer."""
    source = LAUNCH.read_text()
    for package in (
        'buddy_gazebo',
        'buddy_safety',
        'buddy_localization',
        'buddy_mapping',
        'buddy_navigation',
        'buddy_perception',
        'buddy_world_model',
        'buddy_capabilities',
        'buddy_task_executor',
        'buddy_brain',
        'buddy_voice',
    ):
        assert f'"{package}"' in source
    assert '"use_sim_time"' in source
    assert 'localization_mode' in source


def test_bringup_does_not_define_a_motion_bypass():
    """Composition must not create an alternate controller command path."""
    source = '\n'.join(
        path.read_text()
        for path in (ROOT / 'buddy_bringup').rglob('*.py')
        if '/test/' not in str(path)
    )
    assert '/buddy/motion/safe_cmd_vel' not in source
    assert '/buddy/motion/arbitrated_cmd_vel' not in source
    assert 'buddy_base_controller' not in source
