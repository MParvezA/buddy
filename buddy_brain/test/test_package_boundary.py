# Copyright 2026 SyncRobot

from pathlib import Path


def test_dialogue_package_has_no_motion_or_controller_boundary_violation():
    package = Path(__file__).resolve().parents[1]
    source = "\n".join(path.read_text() for path in (package / "buddy_brain").rglob("*.py"))
    forbidden = [
        "/buddy/motion/",
        "nav2",
        "controller_manager",
        "geometry_msgs",
        "subprocess",
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
