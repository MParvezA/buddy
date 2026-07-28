from buddy_navigation.navigation_core import (
    check_preconditions,
    nav2_terminal_outcome,
    Outcome,
)


def test_unknown_location_precedes_runtime_preconditions():
    result = check_preconditions(
        location_found=False,
        localization_available=False,
        safety_state_received=False,
        motion_permitted=False,
    )
    assert result.outcome == Outcome.UNKNOWN_LOCATION


def test_localization_and_safety_preconditions_are_structured():
    unavailable = check_preconditions(
        location_found=True,
        localization_available=False,
        safety_state_received=True,
        motion_permitted=True,
    )
    stopped = check_preconditions(
        location_found=True,
        localization_available=True,
        safety_state_received=True,
        motion_permitted=False,
    )
    assert unavailable.outcome == Outcome.LOCALIZATION_UNAVAILABLE
    assert stopped.outcome == Outcome.SAFETY_STOP


def test_nav2_success_cancel_and_unreachable_mapping():
    succeeded = nav2_terminal_outcome(4, succeeded_status=4, canceled_status=5)
    cancelled = nav2_terminal_outcome(5, succeeded_status=4, canceled_status=5)
    unreachable = nav2_terminal_outcome(6, succeeded_status=4, canceled_status=5)
    assert succeeded.outcome == Outcome.SUCCEEDED
    assert cancelled.outcome == Outcome.CANCELLED
    assert unreachable.outcome == Outcome.UNREACHABLE
