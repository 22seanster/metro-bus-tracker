"""Clock screen: big 12-hour time with blinking colon, small date line."""

from datetime import datetime

from PIL import Image, ImageDraw

from .. import fonts
from ..textdraw import draw_scaled_text, text_width

TIME_COLOR = (255, 255, 255)
DATE_COLOR = (140, 140, 140)


class ClockScreen:
    name = "clock"

    def __init__(self, dwell_seconds: int):
        self.dwell_seconds = dwell_seconds

    def is_active(self, now: datetime) -> bool:
        return True

    def render(self, img: Image.Image, draw: ImageDraw.ImageDraw, now: datetime) -> None:
        hour12 = now.hour % 12 or 12
        colon = ":" if now.second % 2 == 0 else " "
        time_text = f"{hour12}{colon}{now.minute:02d}"

        small = fonts.small()
        w = text_width(time_text, small) * 2
        draw_scaled_text(img, ((64 - w) // 2, 4), time_text, small, TIME_COLOR, scale=2)

        date_text = now.strftime("%a %b %d").upper().replace(" 0", " ")
        tiny = fonts.tiny()
        dw = text_width(date_text, tiny)
        draw.text(((64 - dw) // 2, 24), date_text, font=tiny, fill=DATE_COLOR)
