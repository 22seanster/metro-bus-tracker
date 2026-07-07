from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from app.providers.weather import normalize_weather
from app.screens.weather import WeatherScreen

OPEN_METEO_PAYLOAD = {
    "current": {"temperature_2m": 87.4, "weather_code": 3},
    "daily": {"temperature_2m_max": [95.1], "temperature_2m_min": [78.2]},
}


def test_normalize_weather():
    w = normalize_weather(OPEN_METEO_PAYLOAD)
    assert w.temp_f == 87
    assert w.hi_f == 95
    assert w.lo_f == 78
    assert w.wmo_code == 3


class StubProvider:
    def __init__(self, data):
        self._data = data

    def snapshot(self):
        return self._data

    def is_stale(self):
        return False


def count_lit(img):
    return sum(1 for v in img.convert("L").tobytes() if v)


def render(data):
    img = Image.new("RGB", (64, 32))
    screen = WeatherScreen(dwell_seconds=8, provider=StubProvider(data))
    now = datetime(2026, 7, 7, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    screen.render(img, ImageDraw.Draw(img), now)
    return img, screen


def test_weather_screen_renders_with_data():
    img, _ = render(normalize_weather(OPEN_METEO_PAYLOAD))
    assert count_lit(img) > 60  # icon + big temp + hi/lo line


def test_weather_screen_renders_placeholders_without_data():
    img, _ = render(None)
    assert count_lit(img) > 0  # draws "--" rather than blank/crashing


def test_weather_screen_active_only_with_data():
    now = datetime(2026, 7, 7, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    _, with_data = render(normalize_weather(OPEN_METEO_PAYLOAD))
    assert with_data.is_active(now)
    _, without = render(None)
    assert not without.is_active(now)
