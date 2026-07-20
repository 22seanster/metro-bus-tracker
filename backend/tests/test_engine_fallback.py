"""A broken screen must never turn /frame.bin into a 500 (review finding)."""

from PIL import Image

from app.config import Settings
from app.engine import RenderEngine


class BoomScreen:
    name = "boom"
    dwell_seconds = 5

    def is_active(self, now):
        return True

    def render(self, img, draw, now):
        raise RuntimeError("boom")


class SafeScreen:
    name = "safe"
    dwell_seconds = 5

    def is_active(self, now):
        return False  # rotation only reaches it via the screens[-1] fallback

    def render(self, img, draw, now):
        draw.point((0, 0), fill=(255, 255, 255))


class DoubleBoomScreen(SafeScreen):
    name = "doubleboom"

    def render(self, img, draw, now):
        raise RuntimeError("fallback boom")


def test_broken_screen_falls_back_to_last_screen():
    engine = RenderEngine(Settings(), [BoomScreen(), SafeScreen()])
    img, brightness = engine.render()
    assert isinstance(img, Image.Image)
    assert img.getpixel((0, 0)) == (255, 255, 255)  # the fallback drew
    assert 0 <= brightness <= 255


def test_broken_fallback_serves_blank_frame():
    engine = RenderEngine(Settings(), [BoomScreen(), DoubleBoomScreen()])
    img, _ = engine.render()
    assert img.tobytes() == Image.new("RGB", (64, 32)).tobytes()
