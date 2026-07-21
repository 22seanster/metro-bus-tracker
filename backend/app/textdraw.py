"""Small text helpers for 64x32 rendering with the bundled bitmap fonts."""

import unicodedata
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

# PIL encodes text for bitmap fonts as latin-1, so anything above U+00FF raises
# UnicodeEncodeError. Spotify hands back curly quotes and en-dashes constantly
# ("Don't Stop Me Now" almost always has U+2019), which crashed the render and
# left the screen silently falling back to the clock.
_PUNCTUATION = {
    "‘": "'", "’": "'", "‚": ",", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "―": "-", "−": "-",
    "…": "...", "•": "*", " ": " ",
    "′": "'", "″": '"', "«": '"', "»": '"',
}


@lru_cache(maxsize=256)
def safe_text(text: str) -> str:
    """Coerce text into something the bitmap fonts can actually render.

    Order matters: compose first so "e" + combining acute becomes a single
    latin-1 "é" rather than being flattened; then map smart punctuation to its
    ASCII twin; then, only for characters still out of range, strip accents so
    "ō" degrades to "o" instead of "?". Anything left (CJK, emoji) becomes "?".
    """
    if not text:
        return text
    text = unicodedata.normalize("NFC", text)
    if text.isascii():
        return text
    out = []
    for ch in text:
        ch = _PUNCTUATION.get(ch, ch)
        if all(c <= "ÿ" for c in ch):
            out.append(ch)
            continue
        # Decompose and drop combining marks: "ō" -> "o".
        stripped = "".join(c for c in unicodedata.normalize("NFKD", ch)
                           if not unicodedata.combining(c))
        out.append(stripped if stripped and stripped.isascii() else "?")
    return "".join(out)


def text_width(text: str, font: ImageFont.ImageFont) -> int:
    if not text:
        return 0
    text = safe_text(text)
    left, _, right, _ = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)
    return right - left


def draw_marquee(
    img: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    width: int,
    offset: int = 0,
    gap: int = 12,
) -> None:
    """Draw text scrolling leftwards inside a `width`-px window at `xy`.

    Text that already fits is drawn statically and `offset` is ignored, so
    callers need no branching and short strings stay pixel-identical to a plain
    draw.text().

    Longer text repeats with `gap` blank pixels between the tail and the next
    head, wrapping at `text_width + gap`.

    Composited through a cropped 1-bit mask rather than drawing at a negative x:
    PIL clips at the image edge, not at this window, so a negative-x draw would
    bleed left over whatever shares the row (on the Spotify screen, the album
    art at x=3..18).
    """
    if not text:
        return
    text = safe_text(text)
    x, y = xy
    w = text_width(text, font)
    if w <= width:
        ImageDraw.Draw(img).text(xy, text, font=font, fill=fill)
        return

    _, _, _, bottom = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)
    period = w + gap
    # Two stamps `period` apart cover any window: the crop starts at most at
    # period-1, and w > width guarantees the second stamp reaches its far edge.
    tape = Image.new("1", (period + width, bottom))
    tape_draw = ImageDraw.Draw(tape)
    tape_draw.text((0, 0), text, font=font, fill=1)
    tape_draw.text((period, 0), text, font=font, fill=1)

    start = offset % period
    mask = tape.crop((start, 0, start + width, bottom))
    img.paste(Image.new("RGB", mask.size, fill), (x, y), mask)


def draw_scaled_text(
    img: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    scale: int = 2,
) -> int:
    """Draw text integer-upscaled (chunky pixels). Returns drawn width."""
    text = safe_text(text)
    w = text_width(text, font)
    if w == 0:
        return 0
    _, top, _, bottom = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)
    h = bottom
    tmp = Image.new("1", (w, h))
    ImageDraw.Draw(tmp).text((0, 0), text, font=font, fill=1)
    tmp = tmp.resize((w * scale, h * scale), Image.NEAREST)
    img.paste(Image.new("RGB", tmp.size, fill), xy, tmp)
    return w * scale
