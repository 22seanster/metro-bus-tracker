"""Per-screen render cadence.

A screen may ask for a faster cadence via frame_interval_ms(). That value does
double duty: it sets the engine's memo granularity AND is advertised to the
device in frame header byte [7], so the two can never drift apart.
"""

from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from app.config import Settings
from app.engine import RenderEngine

T0 = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)


class CountingScreen:
    """Counts renders so memo hits are observable."""

    def __init__(self, name="tick", hint=None, active=True, dwell=10):
        self.name = name
        self.dwell_seconds = dwell
        self.renders = 0
        self._hint = hint
        self._active = active
        if hint is not None:
            self.frame_interval_ms = self._frame_interval_ms

    def _frame_interval_ms(self, now):
        return self._hint

    def is_active(self, now):
        return self._active

    def render(self, img, draw, now, elapsed=0.0):
        self.renders += 1
        draw.point((0, 0), fill=(255, 255, 255))


def engine_at(screens, moment):
    """RenderEngine with a controllable clock."""
    eng = RenderEngine(Settings(), screens)
    eng.now = lambda: moment[0]
    return eng


def test_fast_screen_rerenders_within_the_default_memo_window():
    """A 50ms hint must actually produce new frames every 50ms — the 500ms memo
    would otherwise cap any animation at 2fps no matter how fast the device polls."""
    screen = CountingScreen(hint=50)
    moment = [T0]
    eng = engine_at([screen], moment)

    eng.render()
    assert screen.renders == 1

    moment[0] = T0 + timedelta(milliseconds=30)
    eng.render()
    assert screen.renders == 1, "30ms is inside the 50ms bucket"

    moment[0] = T0 + timedelta(milliseconds=70)
    eng.render()
    assert screen.renders == 2, "70ms is a new 50ms bucket"


def test_screen_without_the_hook_keeps_the_500ms_memo():
    screen = CountingScreen(hint=None)
    moment = [T0]
    eng = engine_at([screen], moment)

    eng.render()
    moment[0] = T0 + timedelta(milliseconds=300)
    eng.render()
    assert screen.renders == 1

    moment[0] = T0 + timedelta(milliseconds=600)
    eng.render()
    assert screen.renders == 2


def test_zero_hint_is_treated_as_no_preference():
    screen = CountingScreen(hint=0)
    moment = [T0]
    eng = engine_at([screen], moment)

    eng.render()
    moment[0] = T0 + timedelta(milliseconds=300)
    eng.render()
    assert screen.renders == 1, "0 means no preference, so the 500ms default applies"
    assert eng.frame_bytes()[7] == 0


def test_hint_is_advertised_in_the_frame_header():
    moment = [T0]
    eng = engine_at([CountingScreen(hint=50)], moment)
    assert eng.frame_bytes()[7] == 5  # 50ms in 10ms units


def test_broken_hint_still_serves_a_frame():
    """A screen bug in frame_interval_ms must not take /frame.bin down."""

    class BadHint(CountingScreen):
        def _frame_interval_ms(self, now):
            raise RuntimeError("nope")

    moment = [T0]
    eng = engine_at([BadHint(hint=50)], moment)
    img, brightness = eng.render()
    assert isinstance(img, Image.Image)
    assert eng.frame_bytes()[7] == 0


def test_broken_is_active_still_serves_a_frame():
    class BadActive(CountingScreen):
        def is_active(self, now):
            raise RuntimeError("nope")

    safe = CountingScreen(name="safe")
    moment = [T0]
    eng = engine_at([BadActive(name="bad"), safe], moment)
    img, _ = eng.render()
    assert isinstance(img, Image.Image)
    assert safe.renders == 1, "falls back to the last screen in the registry"


def test_memo_is_never_shared_between_screens():
    """Bucket indices are just integers; without the screen name in the key, two
    screens sharing a bucket would serve each other's pixels."""
    a = CountingScreen(name="a")
    b = CountingScreen(name="b", active=False)
    moment = [T0]
    eng = engine_at([a, b], moment)

    eng.render()
    assert (a.renders, b.renders) == (1, 0)

    # Same instant, same bucket — but now only b is active.
    a._active = False
    b._active = True
    eng.render()
    assert b.renders == 1, "b must render rather than inherit a's cached frame"


def test_memo_hit_returns_the_same_image():
    screen = CountingScreen(hint=50)
    moment = [T0]
    eng = engine_at([screen], moment)
    first, _ = eng.render()
    second, _ = eng.render()
    assert first is second


def test_hint_change_takes_effect_even_between_aliasing_values():
    """`hint or 500` maps 0 and 500 to the same memo divisor, so a screen moving
    between those two values would keep advertising the stale one."""
    screen = CountingScreen(hint=500)
    moment = [T0]
    eng = engine_at([screen], moment)
    assert eng.frame_bytes()[7] == 50  # 500ms

    screen._hint = 0
    moment[0] = T0 + timedelta(milliseconds=200)
    assert eng.frame_bytes()[7] == 0, "must not serve the stale 500ms hint"


def test_empty_registry_serves_a_blank_frame_rather_than_500():
    """main's engine degraded to a blank frame here; keep that hardening."""
    eng = engine_at([], [T0])
    img, _, hint = eng.render_with_hint()
    assert img.tobytes() == Image.new("RGB", (64, 32)).tobytes()
    assert hint == 0
    assert len(eng.frame_bytes()) == 4104


def test_elapsed_is_passed_through_to_render():
    seen = []

    class PhaseScreen(CountingScreen):
        def render(self, img, draw, now, elapsed=0.0):
            seen.append(elapsed)

    moment = [datetime(2026, 7, 20, 12, 0, 3, 250000, tzinfo=timezone.utc)]
    eng = engine_at([PhaseScreen(name="p", dwell=10)], moment)
    eng.render()
    assert seen and seen[0] == pytest.approx(3.25, abs=0.01)
