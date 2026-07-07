"""Spotify now-playing screen: album art thumbnail + track/artist text."""

from datetime import datetime

from PIL import Image, ImageDraw

from .. import fonts, icons
from ..textdraw import text_width

TRACK_COLOR = (255, 255, 255)
ARTIST_COLOR = (30, 215, 96)  # Spotify green
TEXT_X = 22
TEXT_W = 64 - TEXT_X - 1


def _fit(text: str, font, max_w: int) -> str:
    if text_width(text, font) <= max_w:
        return text
    while text and text_width(text + "..", font) > max_w:
        text = text[:-1]
    return text.rstrip() + ".."


def wrap_track(track: str, max_w: int, font=None) -> tuple[str, str]:
    """Wrap onto up to two lines, preserving word order; line 2 is truncated."""
    font = font or fonts.tiny()
    words = track.split()
    line1_words: list[str] = []
    while words:
        candidate = " ".join(line1_words + [words[0]])
        if text_width(candidate, font) > max_w and line1_words:
            break
        line1_words.append(words.pop(0))
    line2 = _fit(" ".join(words), font, max_w) if words else ""
    return " ".join(line1_words), line2


class SpotifyScreen:
    name = "spotify"

    def __init__(self, dwell_seconds: int, provider):
        self.dwell_seconds = dwell_seconds
        self.provider = provider

    def is_active(self, now: datetime) -> bool:
        return self.provider.snapshot() is not None

    def render(self, img: Image.Image, draw: ImageDraw.ImageDraw, now: datetime) -> None:
        np = self.provider.snapshot()
        if np is None:
            return

        if np.art is not None:
            img.paste(np.art, (3, 8))
        else:
            draw.rectangle([3, 8, 18, 23], outline=(80, 80, 80))

        tiny = fonts.tiny()
        # Track: up to two tiny lines, then artist line in Spotify green
        line1, line2 = wrap_track(np.track, TEXT_W, tiny)

        y = 6 if line2 else 9
        draw.text((TEXT_X, y), line1, font=tiny, fill=TRACK_COLOR)
        if line2:
            draw.text((TEXT_X, y + 7), line2, font=tiny, fill=TRACK_COLOR)
        draw.text((TEXT_X, y + (14 if line2 else 8)), _fit(np.artists, tiny, TEXT_W),
                  font=tiny, fill=ARTIST_COLOR)

        if self.provider.is_stale():
            icons.draw_stale_dot(draw)
