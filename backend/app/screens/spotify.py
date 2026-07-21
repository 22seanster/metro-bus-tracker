"""Spotify now-playing screen: album art thumbnail + scrolling track/artist.

The text window is only 41px wide at ~4px per character, so most real track
names overflow. Rather than truncating them with "..", lines that don't fit
scroll; lines that do fit sit still.

Scrolling costs WiFi traffic — the device has to poll fast enough to animate —
so frame_interval_ms() asks for the faster cadence only while something is
actually overflowing.
"""

from datetime import datetime
from functools import lru_cache

from PIL import Image, ImageDraw

from .. import fonts, icons
from ..textdraw import draw_marquee, text_width

TRACK_COLOR = (255, 255, 255)
ARTIST_COLOR = (30, 215, 96)  # Spotify green
TEXT_X = 22
TEXT_W = 64 - TEXT_X - 1
TRACK_Y = 11
ARTIST_Y = 19

SCROLL_FRAME_MS = 100
SCROLL_PX_PER_SEC = 10  # exactly 1px per frame at SCROLL_FRAME_MS
SCROLL_GAP = 12  # blank px between the tail and the wrapped head
SCROLL_HOLD_SEC = 1.0  # pause at the start so the first word is readable


@lru_cache(maxsize=64)
def _overflows(text: str) -> bool:
    # Cached: this runs on every request, and at a 100ms cadence that is 10x/sec
    # for a string that only changes when the track does.
    return text_width(text, fonts.tiny()) > TEXT_W


class SpotifyScreen:
    name = "spotify"

    def __init__(self, dwell_seconds: int, provider, scroll: bool = True):
        self.dwell_seconds = dwell_seconds
        self.provider = provider
        # Kill switch (SPOTIFY_SCROLL). Turning this off drops the advertised
        # cadence back to 0, so the device returns to its default poll rate on
        # the very next frame — no rebuild, no OTA, no reboot. It is the only
        # recovery lever that works once the fast-polling firmware is already
        # deployed, so keep it a plain flag with no other behaviour attached.
        self.scroll = scroll

    def is_active(self, now: datetime) -> bool:
        return self.provider.snapshot() is not None

    def frame_interval_ms(self, now: datetime) -> int:
        """0 = no preference, so the device stays on its own default poll rate."""
        if not self.scroll:
            return 0
        np = self.provider.snapshot()
        if np is None:
            return 0
        if _overflows(np.track) or _overflows(np.artists):
            return SCROLL_FRAME_MS
        return 0

    def render(self, img: Image.Image, draw: ImageDraw.ImageDraw, now: datetime,
               elapsed: float = 0.0) -> None:
        np = self.provider.snapshot()
        if np is None:
            return

        if np.art is not None:
            img.paste(np.art, (3, 8))
        else:
            draw.rectangle([3, 8, 18, 23], outline=(80, 80, 80))

        tiny = fonts.tiny()
        # Motion comes from elapsed-in-dwell, so the scroll restarts each time the
        # screen comes around rather than dropping in at an arbitrary position.
        # Pinned at 0 when disabled: long lines freeze showing their head, which
        # is the pre-scrolling behaviour minus the ".." suffix.
        offset = int(max(0.0, elapsed - SCROLL_HOLD_SEC) * SCROLL_PX_PER_SEC) if self.scroll else 0
        draw_marquee(img, (TEXT_X, TRACK_Y), np.track, tiny, TRACK_COLOR,
                     TEXT_W, offset=offset, gap=SCROLL_GAP)
        draw_marquee(img, (TEXT_X, ARTIST_Y), np.artists, tiny, ARTIST_COLOR,
                     TEXT_W, offset=offset, gap=SCROLL_GAP)

        if self.provider.is_stale():
            icons.draw_stale_dot(draw)
