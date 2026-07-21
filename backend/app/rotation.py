"""Deterministic wall-clock screen rotation.

The current screen is a pure function of the epoch second, so any number of
polling clients (ESP32, browser preview) see the same coherent rotation with
no server-side session state.
"""

from datetime import datetime
from typing import Sequence

from .screens.base import Screen


def screen_slot(now: datetime, screens: Sequence[Screen]) -> tuple[Screen, float]:
    """The current screen and how many seconds we are into its dwell, in [0, dwell).

    Animated screens need the elapsed value so motion restarts when the screen
    comes into view; deriving it from raw epoch time instead would drop you into
    the middle of a scroll at an arbitrary position.

    Elapsed is a float — whole seconds would pin any animation to 1fps.

    Caveat: `cycle` changes whenever a screen's is_active() flips (e.g. Spotify
    starting or stopping), which re-phases every screen mid-dwell. Rare and
    self-correcting. Do not "fix" it with a dynamic dwell_seconds — that would
    re-phase the rotation on every track change instead.
    """
    if not screens:
        raise ValueError("no screens registered")
    active = [s for s in screens if s.is_active(now)]
    if not active:
        return screens[-1], 0.0  # registry keeps the always-on clock last
    cycle = sum(s.dwell_seconds for s in active)
    t = now.timestamp() % cycle
    for s in active:
        if t < s.dwell_seconds:
            return s, t
        t -= s.dwell_seconds
    return active[-1], 0.0  # unreachable; guards float edge cases


def current_screen(now: datetime, screens: Sequence[Screen]) -> Screen:
    # Delegates so the modulo arithmetic lives in exactly one place. Selection is
    # unchanged from the previous int()-truncating version: cycle is an integer,
    # so floor(ts) % cycle == floor(ts % cycle).
    return screen_slot(now, screens)[0]
