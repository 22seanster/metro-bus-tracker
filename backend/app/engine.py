"""Turns the screen registry into frames on demand.

Rendering is pull-based (each HTTP request), memoized per half-second so the
ESP32 and any preview browsers concurrently trigger at most ~2 renders/sec.
Render only reads provider snapshots; it never touches the network.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from .config import Settings
from .frame import compute_brightness, pack_frame
from .rotation import current_screen
from .screens.base import Screen

log = logging.getLogger(__name__)


class RenderEngine:
    def __init__(self, settings: Settings, screens: list[Screen]):
        self.settings = settings
        self.screens = screens
        self.tz = ZoneInfo(settings.app_tz)
        # Single attribute, written last: the frame endpoints are sync `def`s,
        # so FastAPI runs them concurrently in threads. A (key, value) pair in
        # two attributes could be observed half-updated.
        self._memo: tuple[int, Image.Image, int] | None = None

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def render(self) -> tuple[Image.Image, int]:
        """Returns (64x32 RGB image, brightness)."""
        now = self.now()
        key = int(now.timestamp() * 2)
        memo = self._memo
        if memo is not None and memo[0] == key:
            return memo[1], memo[2]
        img = Image.new("RGB", (64, 32))
        try:
            screen = current_screen(now, self.screens)
            screen.render(img, ImageDraw.Draw(img), now)
        except Exception:
            # One screen bug must never turn /frame.bin into a 500 — the device
            # would silently freeze on its last frame. Fall back to the always-on
            # clock (registry keeps it last); worst case, serve a blank frame.
            log.exception("screen render failed; falling back to clock")
            img = Image.new("RGB", (64, 32))
            try:
                self.screens[-1].render(img, ImageDraw.Draw(img), now)
            except Exception:
                log.exception("fallback screen render failed; serving blank frame")
                img = Image.new("RGB", (64, 32))
        s = self.settings
        brightness = compute_brightness(
            now, day=s.brightness, night=s.night_brightness,
            night_start=s.night_start, night_end=s.night_end,
        )
        self._memo = (key, img, brightness)
        return img, brightness

    def frame_bytes(self) -> bytes:
        img, brightness = self.render()
        return pack_frame(img, brightness)

    def current_screen_name(self) -> str:
        return current_screen(self.now(), self.screens).name
