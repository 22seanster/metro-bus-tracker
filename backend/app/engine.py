"""Turns the screen registry into frames on demand.

Rendering is pull-based (each HTTP request), memoized per half-second so the
ESP32 and any preview browsers concurrently trigger at most ~2 renders/sec.
Render only reads provider snapshots; it never touches the network.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from .config import Settings
from .frame import compute_brightness, pack_frame
from .rotation import current_screen
from .screens.base import Screen


class RenderEngine:
    def __init__(self, settings: Settings, screens: list[Screen]):
        self.settings = settings
        self.screens = screens
        self.tz = ZoneInfo(settings.app_tz)
        self._memo_key: int | None = None
        self._memo: tuple[Image.Image, int] | None = None

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def render(self) -> tuple[Image.Image, int]:
        """Returns (64x32 RGB image, brightness)."""
        now = self.now()
        key = int(now.timestamp() * 2)
        if self._memo is not None and self._memo_key == key:
            return self._memo
        img = Image.new("RGB", (64, 32))
        screen = current_screen(now, self.screens)
        screen.render(img, ImageDraw.Draw(img), now)
        s = self.settings
        brightness = compute_brightness(
            now, day=s.brightness, night=s.night_brightness,
            night_start=s.night_start, night_end=s.night_end,
        )
        self._memo_key, self._memo = key, (img, brightness)
        return img, brightness

    def frame_bytes(self) -> bytes:
        img, brightness = self.render()
        return pack_frame(img, brightness)

    def current_screen_name(self) -> str:
        return current_screen(self.now(), self.screens).name
