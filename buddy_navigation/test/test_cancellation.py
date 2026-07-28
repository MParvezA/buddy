from types import SimpleNamespace

from buddy_navigation.cancellation import confirm_downstream_cancel


class CompleteFuture:

    def __init__(self, value=None, *, error=None):
        self._value = value
        self._error = error

    def done(self):
        return True

    def exception(self):
        return self._error

    def result(self):
        if self._error is not None:
            raise self._error
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


def test_cancel_future_exception_is_structured_as_unconfirmed():
    nav2 = FakeNav2Goal()
    nav2.cancel_goal_async = lambda: CompleteFuture(
        error=RuntimeError('cancel transport lost')
    )

    result = confirm_downstream_cancel(
        nav2,
        CompleteFuture(SimpleNamespace(status=5)),
        canceled_status=5,
        timeout_sec=0.1,
    )

    assert result.confirmed is False
    assert 'acknowledgement failed' in result.message
    assert 'cancel transport lost' in result.message


def test_cancel_ack_then_result_exception_is_structured_as_unconfirmed():
    nav2 = FakeNav2Goal()

    result = confirm_downstream_cancel(
        nav2,
        CompleteFuture(error=RuntimeError('result transport lost')),
        canceled_status=5,
        timeout_sec=0.1,
    )

    assert result.confirmed is False
    assert nav2.cancel_calls == 1
    assert nav2.command_active is False
    assert 'terminal result failed' in result.message
    assert 'result transport lost' in result.message
