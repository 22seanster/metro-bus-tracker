"""Small text helpers for 64x32 rendering with the bundled bitmap fonts."""

from PIL import Image, ImageDraw, ImageFont


def text_width(text: str, font: ImageFont.ImageFont) -> int:
    if not text:
        return 0
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
