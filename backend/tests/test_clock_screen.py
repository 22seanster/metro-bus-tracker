from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from app.screens.clock import ClockScreen

TZ = ZoneInfo("America/Chicago")


def render_at(now: datetime) -> Image.Image:
    img = Image.new("RGB", (64, 32))
    ClockScreen(dwell_seconds=8).render(img, ImageDraw.Draw(img), now)
    return img


def count_lit(img: Image.Image) -> int:
    return sum(1 for v in img.convert("L").tobytes() if v)


def test_clock_is_always_active():
    assert ClockScreen(dwell_seconds=8).is_active(datetime(2026, 7, 7, 3, 0, tzinfo=TZ))


def test_clock_renders_time_and_date():
    img = render_at(datetime(2026, 7, 7, 14, 35, 0, tzinfo=TZ))
    assert count_lit(img) > 50  # big HH:MM plus date line


def test_colon_blinks_on_odd_seconds():
    even = render_at(datetime(2026, 7, 7, 14, 35, 0, tzinfo=TZ))
    odd = render_at(datetime(2026, 7, 7, 14, 35, 1, tzinfo=TZ))
    assert count_lit(even) > count_lit(odd)  # colon hidden on odd seconds
