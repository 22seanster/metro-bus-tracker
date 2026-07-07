"""Small text helpers for 64x32 rendering with the bundled bitmap fonts."""

from PIL import Image, ImageDraw, ImageFont


def text_width(text: str, font: ImageFont.ImageFont) -> int:
    if not text:
        return 0
    left, _, right, _ = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)
    return right - left


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
