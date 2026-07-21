"""Weather screen: condition icon, big current temp, daily high/low."""

from datetime import datetime

from PIL import Image, ImageDraw

from .. import fonts, icons
from ..textdraw import draw_scaled_text, text_width

TEMP_COLOR = (255, 255, 255)
HILO_COLOR = (140, 140, 140)


class WeatherScreen:
    name = "weather"

    def __init__(self, dwell_seconds: int, provider):
        self.dwell_seconds = dwell_seconds
        self.provider = provider

    def is_active(self, now: datetime) -> bool:
        return self.provider.snapshot() is not None

    def render(self, img: Image.Image, draw: ImageDraw.ImageDraw, now: datetime,
               elapsed: float = 0.0) -> None:
        w = self.provider.snapshot()
        if w is None:
            small = fonts.small()
            draw.text((26, 12), "--", font=small, fill=HILO_COLOR)
            return

        icons.draw_weather_icon(draw, icons.bucket(w.wmo_code), 3, 5)

        small = fonts.small()
        temp_text = str(w.temp_f)
        x = 24
        used = draw_scaled_text(img, (x, 4), temp_text, small, TEMP_COLOR, scale=2)
        icons.draw_degree(draw, x + used + 2, 5, TEMP_COLOR, scale=2)

        tiny = fonts.tiny()
        hilo = f"H {w.hi_f}  L {w.lo_f}"
        tw = text_width(hilo, tiny)
        draw.text(((64 - tw) // 2, 25), hilo, font=tiny, fill=HILO_COLOR)

        if self.provider.is_stale():
            icons.draw_stale_dot(draw)
