"""Screen contract. Adding a new screen (e.g. Spotify now-playing) means:
implement this protocol, then append an instance to the registry in app/main.py.
The frame protocol and firmware never change."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from PIL import Image, ImageDraw


@runtime_checkable
class Screen(Protocol):
    name: str
    dwell_seconds: int

    def is_active(self, now: datetime) -> bool:
        """Whether this screen should appear in the rotation right now."""
        ...

    def render(self, img: Image.Image, draw: ImageDraw.ImageDraw, now: datetime,
               elapsed: float = 0.0) -> None:
        """Draw onto a 64x32 black RGB image.

        `elapsed` is seconds into this screen's dwell, for animation. Derive
        motion from it (or from `now`) rather than from an accumulated counter:
        /frame.bin is a sync def served from FastAPI's threadpool, so per-screen
        mutable state would be a race between concurrent requests.
        """
        ...

    # Optional hook, deliberately not part of the Protocol so screens that don't
    # animate need not declare it — the engine looks it up with getattr:
    #
    #     def frame_interval_ms(self, now: datetime) -> int
    #
    # Desired render cadence in milliseconds; 0 means "no preference", which
    # leaves the device on its own default poll rate. Only return a small value
    # while actually animating: it drives the device's poll rate, so a screen
    # that always asks for one multiplies WiFi traffic for nothing.
