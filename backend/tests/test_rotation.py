from datetime import datetime, timezone

import pytest

from app.rotation import current_screen, screen_slot


class FakeScreen:
    def __init__(self, name, dwell, active=True):
        self.name = name
        self.dwell_seconds = dwell
        self._active = active

    def is_active(self, now):
        return self._active

    def render(self, img, draw, now, elapsed=0.0):
        pass


def at_epoch(epoch: float) -> datetime:
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


# --- screen_slot: the screen plus how far into its dwell we are ---------------


def test_slot_elapsed_resets_at_each_screen_boundary():
    a = FakeScreen("a", 10)
    b = FakeScreen("b", 5)
    screens = [a, b]
    assert screen_slot(at_epoch(0), screens) == (a, 0.0)
    assert screen_slot(at_epoch(9), screens) == (a, 9.0)
    assert screen_slot(at_epoch(10), screens) == (b, 0.0)  # b's turn starts over
    assert screen_slot(at_epoch(14), screens) == (b, 4.0)
    assert screen_slot(at_epoch(15), screens) == (a, 0.0)  # wraps


def test_slot_elapsed_keeps_sub_second_resolution():
    """A 20px/sec scroll needs finer than whole seconds; the old int() truncation
    would have pinned the animation to 1fps."""
    a = FakeScreen("a", 10)
    _, elapsed = screen_slot(at_epoch(3.25), [a])
    assert elapsed == pytest.approx(3.25)


def test_slot_elapsed_always_within_dwell():
    screens = [FakeScreen("a", 10), FakeScreen("b", 5)]
    for hundredth in range(0, 1500):
        screen, elapsed = screen_slot(at_epoch(hundredth / 100), screens)
        assert 0.0 <= elapsed < screen.dwell_seconds


def test_slot_agrees_with_current_screen_across_a_full_cycle():
    """current_screen must keep its exact present behaviour: it now delegates to
    screen_slot, and floor(ts) % cycle == floor(ts % cycle) for integer cycles."""
    screens = [FakeScreen("a", 10), FakeScreen("b", 5)]
    for hundredth in range(0, 3000):
        now = at_epoch(1_000_000 + hundredth / 100)
        assert current_screen(now, screens) is screen_slot(now, screens)[0]


def test_slot_falls_back_with_zero_elapsed():
    a = FakeScreen("a", 10, active=False)
    b = FakeScreen("b", 5, active=False)
    assert screen_slot(at_epoch(3), [a, b]) == (b, 0.0)


def test_slot_rejects_empty_registry():
    with pytest.raises(ValueError):
        screen_slot(at_epoch(0), [])
