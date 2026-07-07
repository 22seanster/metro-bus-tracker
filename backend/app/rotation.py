"""Deterministic wall-clock screen rotation.

The current screen is a pure function of the epoch second, so any number of
polling clients (ESP32, browser preview) see the same coherent rotation with
no server-side session state.
"""

from datetime import datetime
from typing import Sequence

from .screens.base import Screen


def current_screen(now: datetime, screens: Sequence[Screen]) -> Screen:
    if not screens:
        raise ValueError("no screens registered")
    active = [s for s in screens if s.is_active(now)]
    if not active:
        return screens[-1]  # registry keeps the always-on clock last
    cycle = sum(s.dwell_seconds for s in active)
    t = int(now.timestamp()) % cycle
    for s in active:
        if t < s.dwell_seconds:
            return s
        t -= s.dwell_seconds
    return active[-1]  # unreachable; guards float edge cases
