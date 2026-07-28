from types import SimpleNamespace

from buddy_navigation.cancellation import confirm_downstream_cancel


class CompleteFuture:

    def __init__(self, value):
        self._value = value

    def done(self):
        return True

    def result(self):
        return self._value


class FakeNav2Goal:

    def __init__(self):
        self.cancel_calls = 0
        self.command_active = True

    def cancel_goal_async(self):
        self.cancel_calls += 1
        self.command_active = False
        response = SimpleNamespace(goals_canceling=[object()])
        return CompleteFuture(response)


def test_cancel_reaches_fake_nav2_and_confirms_command_ceased():
    nav2 = FakeNav2Goal()
    terminal = CompleteFuture(SimpleNamespace(status=5))
    result = confirm_downstream_cancel(
        nav2,
        terminal,
        canceled_status=5,
        timeout_sec=0.1,
    )
    assert result.confirmed
    assert nav2.cancel_calls == 1
    assert nav2.command_active is False


def test_unacknowledged_cancel_is_not_reported_as_safe():
    nav2 = FakeNav2Goal()
    nav2.cancel_goal_async = lambda: CompleteFuture(
        SimpleNamespace(goals_canceling=[])
    )
    terminal = CompleteFuture(SimpleNamespace(status=5))
    result = confirm_downstream_cancel(
        nav2,
        terminal,
        canceled_status=5,
        timeout_sec=0.1,
    )
    assert result.confirmed is False
    assert 'did not acknowledge' in result.message
