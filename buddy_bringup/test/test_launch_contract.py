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


def test_local_providers_are_explicit_and_fake_providers_remain_defaults():
    """Real providers require opt-in and retain the four-core profile bounds."""
    source = LAUNCH.read_text()
    assert '"model_provider",' in source
    assert '"speech_provider",' in source
    assert 'default_value="fake"' in source
    assert '"voice_input_mode",' in source
    assert 'choices=["fake", "external"]' in source
    assert 'executable="local_speak_server"' in source
    assert '"llama_cpp_threads", default_value="3"' in source
    assert '"llama_cpp_context_tokens", default_value="4096"' in source
    assert '"llama_cpp_output_tokens", default_value="256"' in source
    assert '"llama_cpp_timeout_seconds", default_value="20.0"' in source


def test_local_provider_composition_does_not_launch_an_interactive_terminal():
    """Keyboard-driven PTT remains a separate operator process."""
    source = LAUNCH.read_text()
    assert 'terminal_ptt' not in source


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
