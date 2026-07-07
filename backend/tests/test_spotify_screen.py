from datetime import datetime, timezone

from PIL import Image, ImageDraw

from app.providers.spotify import NowPlaying
from app.screens.spotify import SpotifyScreen

NOW = datetime(2026, 7, 7, 20, 0, tzinfo=timezone.utc)


class Stub:
    def __init__(self, np):
        self._np = np

    def snapshot(self):
        return self._np

    def is_stale(self):
        return False


def make_np(art=True):
    img = Image.new("RGB", (16, 16), (200, 60, 20)) if art else None
    return NowPlaying(account="sean", track="Texas Sun", artists="Khruangbin, Leon Bridges",
                      art_url="u", device_name="Kitchen", is_playing=True, art=img)


def count_lit(img):
    return sum(1 for v in img.convert("L").tobytes() if v)


def render(np):
    img = Image.new("RGB", (64, 32))
    SpotifyScreen(dwell_seconds=10, provider=Stub(np)).render(img, ImageDraw.Draw(img), NOW)
    return img


def test_active_only_when_playing():
    assert SpotifyScreen(dwell_seconds=10, provider=Stub(make_np())).is_active(NOW)
    assert not SpotifyScreen(dwell_seconds=10, provider=Stub(None)).is_active(NOW)


def test_renders_album_art_block():
    img = render(make_np())
    assert img.getpixel((6, 15)) == (200, 60, 20)  # inside the 16x16 art area
    assert count_lit(img) > 200


def test_renders_without_art():
    img = render(make_np(art=False))
    assert count_lit(img) > 30  # text still drawn
