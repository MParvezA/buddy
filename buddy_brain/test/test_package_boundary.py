# Copyright 2026 SyncRobot

from pathlib import Path


def test_dialogue_package_has_no_motion_or_controller_boundary_violation():
    package = Path(__file__).resolve().parents[1]
    implementation = package / "buddy_brain"
    source = "\n".join(
        path.read_text()
        for path in implementation.rglob("*.py")
        if path.name != "model_provider.py"
    )
    forbidden = [
        "/buddy/motion/",
        "nav2",
        "controller_manager",
        "geometry_msgs",
        "os.system",
        "buddy_navigation",
        "buddy_task_executor",
        "buddy_voice",
    ]
    assert all(term not in source for term in forbidden)
    assert '"/buddy/voice/utterance"' in source
    assert '"/buddy/status"' in source
    assert '"/buddy/world/summary"' in source
    assert '"/buddy/tasks/execute"' in source
    assert '"/buddy/voice/speak"' in source
    assert "/buddy/tasks/proposed" not in source
    provider_source = (implementation / "model_provider.py").read_text()
    assert "subprocess.Popen" in provider_source
    assert "shell=True" not in provider_source
    assert "subprocess" not in source
