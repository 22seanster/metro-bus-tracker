"""Hand-drawn 12x12 weather glyphs and tiny indicators, painted with ImageDraw."""

from PIL import ImageDraw

SUN = (255, 200, 40)
CLOUD = (170, 175, 185)
DARK_CLOUD = (120, 125, 135)
RAIN = (80, 140, 255)
SNOW = (230, 240, 255)
BOLT = (255, 220, 60)
FOG = (150, 150, 155)
STALE = (255, 170, 30)


def bucket(wmo_code: int) -> str:
    if wmo_code == 0:
        return "clear"
    if wmo_code in (1, 2):
        return "partly"
    if wmo_code == 3:
        return "cloudy"
    if wmo_code in (45, 48):
        return "fog"
    if 51 <= wmo_code <= 67 or 80 <= wmo_code <= 82:
        return "rain"
    if 71 <= wmo_code <= 77 or wmo_code in (85, 86):
        return "snow"
    if wmo_code >= 95:
        return "storm"
    return "cloudy"


def _sun(d: ImageDraw.ImageDraw, x: int, y: int) -> None:
    d.ellipse([x + 3, y + 3, x + 8, y + 8], fill=SUN)
    for a, b in [((x + 5, y), (x + 6, y + 1)), ((x + 5, y + 10), (x + 6, y + 11)),
                 ((x, y + 5), (x + 1, y + 6)), ((x + 10, y + 5), (x + 11, y + 6))]:
        d.rectangle([a, b], fill=SUN)


def _cloud(d: ImageDraw.ImageDraw, x: int, y: int, color=CLOUD) -> None:
    d.ellipse([x, y + 4, x + 6, y + 9], fill=color)
    d.ellipse([x + 3, y + 2, x + 9, y + 8], fill=color)
    d.rectangle([x + 2, y + 6, x + 10, y + 9], fill=color)


def draw_weather_icon(d: ImageDraw.ImageDraw, kind: str, x: int, y: int) -> None:
    if kind == "clear":
        _sun(d, x, y)
    elif kind == "partly":
        _sun(d, x, y - 1)
        _cloud(d, x + 1, y + 2)
    elif kind == "cloudy":
        _cloud(d, x + 1, y + 1)
    elif kind == "fog":
        for row in (y + 2, y + 5, y + 8):
            d.rectangle([x, row, x + 11, row + 1], fill=FOG)
    elif kind == "rain":
        _cloud(d, x + 1, y, DARK_CLOUD)
        for i, dx in enumerate((1, 5, 9)):
            d.line([x + dx, y + 9, x + dx - 1, y + 11], fill=RAIN)
    elif kind == "snow":
        _cloud(d, x + 1, y, DARK_CLOUD)
        for dx in (1, 5, 9):
            d.point([(x + dx, y + 10)], fill=SNOW)
            d.point([(x + dx + 1, y + 11)], fill=SNOW)
    elif kind == "storm":
        _cloud(d, x + 1, y, DARK_CLOUD)
        d.line([x + 6, y + 8, x + 4, y + 11], fill=BOLT, width=1)
        d.line([x + 5, y + 9, x + 7, y + 10], fill=BOLT, width=1)


def draw_stale_dot(d: ImageDraw.ImageDraw) -> None:
    """2x2 amber dot, top-right corner: data is stale."""
    d.rectangle([61, 0, 62, 1], fill=STALE)


def draw_degree(d: ImageDraw.ImageDraw, x: int, y: int, color, scale: int = 1) -> int:
    """Open square degree mark; returns width used."""
    s = 2 * scale
    d.rectangle([x, y, x + s - 1, y + s - 1], outline=color)
    return s + scale
