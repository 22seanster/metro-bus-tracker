from datetime import datetime, timezone

from app.rotation import current_screen


class FakeScreen:
    def __init__(self, name, dwell, active=True):
        self.name = name
        self.dwell_seconds = dwell
        self._active = active

    def is_active(self, now):
        return self._active

    def render(self, img, draw, now):
        pass


def at_epoch(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def test_slots_follow_dwell_times():
    a = FakeScreen("a", 10)
    b = FakeScreen("b", 5)
    screens = [a, b]
    # cycle = 15s: [0,10) -> a, [10,15) -> b
    assert current_screen(at_epoch(0), screens) is a
    assert current_screen(at_epoch(9), screens) is a
    assert current_screen(at_epoch(10), screens) is b
    assert current_screen(at_epoch(14), screens) is b
    assert current_screen(at_epoch(15), screens) is a  # wraps


def test_deterministic_across_calls():
    screens = [FakeScreen("a", 10), FakeScreen("b", 5)]
    assert current_screen(at_epoch(1_000_007), screens) is current_screen(at_epoch(1_000_007), screens)


def test_inactive_screen_skipped():
    a = FakeScreen("a", 10, active=False)
    b = FakeScreen("b", 5)
    # Only b active -> always b
    assert current_screen(at_epoch(0), [a, b]) is b
    assert current_screen(at_epoch(12), [a, b]) is b


def test_all_inactive_falls_back_to_last_screen():
    a = FakeScreen("a", 10, active=False)
    b = FakeScreen("b", 5, active=False)
    # Fallback: the last screen in the list (registry puts clock last)
    assert current_screen(at_epoch(3), [a, b]) is b
