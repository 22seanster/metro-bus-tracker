"""Bus arrivals screen: one row per route, colored badge + next arrival minutes."""

from datetime import datetime

from PIL import Image, ImageDraw

from .. import fonts, icons
from ..textdraw import text_width

TEXT_COLOR = (255, 255, 255)
UNIT_COLOR = (150, 150, 150)
NONE_COLOR = (110, 110, 110)
MAX_ARRIVALS_PER_ROUTE = 2


def _hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


class BusScreen:
    name = "bus"

    def __init__(self, dwell_seconds: int, provider, route_ids: list[str],
                 labels: dict[str, str], colors: dict[str, str]):
        self.dwell_seconds = dwell_seconds
        self.provider = provider
        self.route_ids = route_ids
        self.labels = labels
        self.colors = {r: _hex_to_rgb(c) for r, c in colors.items()}

    def is_active(self, now: datetime) -> bool:
        return bool(self.provider.snapshot())

    def render(self, img: Image.Image, draw: ImageDraw.ImageDraw, now: datetime) -> None:
        arrivals = self.provider.snapshot() or []
        small = fonts.small()
        tiny = fonts.tiny()

        for row, route_id in enumerate(self.route_ids[:2]):
            y = 1 + row * 16
            color = self.colors.get(route_id, (90, 90, 90))
            label = self.labels.get(route_id, route_id)

            draw.rounded_rectangle([1, y, 14, y + 12], radius=2, fill=color)
            lw = text_width(label, small)
            draw.text((1 + (14 - lw) // 2, y + 3), label, font=small, fill=TEXT_COLOR)

            mins = [a.minutes for a in arrivals if a.route_id == route_id][:MAX_ARRIVALS_PER_ROUTE]
            x = 19
            if not mins:
                draw.text((x, y + 3), "--", font=small, fill=NONE_COLOR)
                continue
            for i, m in enumerate(mins):
                text = str(m)
                draw.text((x, y + 3), text, font=small, fill=TEXT_COLOR)
                x += text_width(text, small)
                if i == len(mins) - 1:
                    draw.text((x + 1, y + 5), "m", font=tiny, fill=UNIT_COLOR)
                else:
                    draw.text((x + 1, y + 3), ",", font=small, fill=UNIT_COLOR)
                    x += 4

        if self.provider.is_stale():
            icons.draw_stale_dot(draw)
