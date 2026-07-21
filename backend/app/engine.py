"""Turns the screen registry into frames on demand.

Rendering is pull-based (each HTTP request), memoized so that concurrent clients
(the ESP32, any preview browsers) trigger at most one render per bucket. The
bucket is normally half a second, but an animating screen can ask for a finer
one via frame_interval_ms() — the Spotify screen does this while scrolling.

That same interval is advertised to the device in frame header byte [7], so the
render cadence and the device's poll rate are driven by one number and cannot
drift apart.

Note screen selection (and therefore is_active) now runs *before* the memo
check, since the memo key depends on which screen is up. That's microseconds
even at 20 requests/sec. Render only reads provider snapshots; it never touches
the network.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from .config import Settings
from .frame import compute_brightness, pack_frame
from .rotation import current_screen, screen_slot
from .screens.base import Screen

log = logging.getLogger(__name__)

DEFAULT_MEMO_MS = 500


class RenderEngine:
    def __init__(self, settings: Settings, screens: list[Screen]):
        self.settings = settings
        self.screens = screens
        self.tz = ZoneInfo(settings.app_tz)
        # Single attribute, written last: the frame endpoints are sync `def`s,
        # so FastAPI runs them concurrently in threads. A (key, value) pair in
        # two attributes could be observed half-updated.
        self._memo: tuple[tuple[str, int], Image.Image, int, int] | None = None

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def _cadence_hint(self, screen: Screen, now: datetime) -> int:
        """Screen's requested cadence in ms, 0 = no preference.

        getattr rather than a Protocol member so screens that never animate
        (bus, weather, clock) don't have to declare it.
        """
        getter = getattr(screen, "frame_interval_ms", None)
        if getter is None:
            return 0
        try:
            return max(0, int(getter(now)))
        except Exception:
            log.exception("frame_interval_ms failed; falling back to default cadence")
            return 0

    def render(self) -> tuple[Image.Image, int]:
        """Returns (64x32 RGB image, brightness)."""
        img, brightness, _ = self.render_with_hint()
        return img, brightness

    def render_with_hint(self) -> tuple[Image.Image, int, int]:
        """Returns (64x32 RGB image, brightness, cadence hint in ms)."""
        now = self.now()
        screen, elapsed = None, 0.0
        try:
            screen, elapsed = screen_slot(now, self.screens)
        except Exception:
            # A screen's is_active() raising must not 500 the frame endpoints.
            # screens[-1] is read defensively: an empty registry must still
            # degrade to a blank frame rather than an IndexError.
            log.exception("screen selection failed; falling back to clock")
            if self.screens:
                screen = self.screens[-1]

        hint = self._cadence_hint(screen, now) if screen is not None else 0
        # Key carries the screen name AND the hint. The name because bucket
        # indices are plain integers, so two screens could otherwise land in the
        # same bucket and be served each other's pixels. The hint because
        # `hint or DEFAULT_MEMO_MS` aliases 0 and 500 to one divisor, which would
        # let a screen moving between those two keep advertising the stale one.
        key = (getattr(screen, "name", ""), hint,
               int(now.timestamp() * 1000) // (hint or DEFAULT_MEMO_MS))
        memo = self._memo
        if memo is not None and memo[0] == key:
            return memo[1], memo[2], memo[3]

        img = Image.new("RGB", (64, 32))
        try:
            if screen is None:
                raise RuntimeError("no screens registered")
            screen.render(img, ImageDraw.Draw(img), now, elapsed)
        except Exception:
            # One screen bug must never turn /frame.bin into a 500 — the device
            # would silently freeze on its last frame. Fall back to the always-on
            # clock (registry keeps it last); worst case, serve a blank frame.
            log.exception("screen render failed; falling back to clock")
            img = Image.new("RGB", (64, 32))
            try:
                self.screens[-1].render(img, ImageDraw.Draw(img), now, 0.0)
            except Exception:
                log.exception("fallback screen render failed; serving blank frame")
                img = Image.new("RGB", (64, 32))
        s = self.settings
        brightness = compute_brightness(
            now, day=s.brightness, night=s.night_brightness,
            night_start=s.night_start, night_end=s.night_end,
        )
        self._memo = (key, img, brightness, hint)
        return img, brightness, hint

    def frame_bytes(self) -> bytes:
        img, brightness, hint = self.render_with_hint()
        return pack_frame(img, brightness, poll_ms=hint)

    def current_screen_name(self) -> str:
        return current_screen(self.now(), self.screens).name
