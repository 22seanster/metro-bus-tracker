"""Binary frame format for the ESP32 client.

Layout (4104 bytes total):
  [0:2]  magic "MB"
  [2]    version (1)
  [3]    flags (bit0 = blank display; reserved)
  [4]    brightness 0-255
  [5]    width (64)
  [6]    height (32)
  [7]    reserved
  [8:]   64*32 pixels, RGB565 little-endian, row-major from top-left
"""

from datetime import datetime, time

from PIL import Image

WIDTH = 64
HEIGHT = 32
HEADER_SIZE = 8
FRAME_SIZE = HEADER_SIZE + WIDTH * HEIGHT * 2

MAGIC = b"MB"
VERSION = 1


def pack_frame(img: Image.Image, brightness: int, flags: int = 0) -> bytes:
    if img.size != (WIDTH, HEIGHT):
        raise ValueError(f"expected {WIDTH}x{HEIGHT} image, got {img.size}")
    header = bytes([MAGIC[0], MAGIC[1], VERSION, flags, brightness & 0xFF, WIDTH, HEIGHT, 0])
    pixels = bytearray(WIDTH * HEIGHT * 2)
    raw = img.convert("RGB").tobytes()  # r,g,b per pixel, row-major
    for i in range(WIDTH * HEIGHT):
        r, g, b = raw[3 * i], raw[3 * i + 1], raw[3 * i + 2]
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        pixels[2 * i] = v & 0xFF
        pixels[2 * i + 1] = v >> 8
    return header + bytes(pixels)


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def compute_brightness(now: datetime, *, day: int, night: int, night_start: str, night_end: str) -> int:
    start = _parse_hhmm(night_start)
    end = _parse_hhmm(night_end)
    t = now.time()
    if start <= end:
        in_night = start <= t < end
    else:  # window wraps midnight, e.g. 22:00-06:30
        in_night = t >= start or t < end
    return night if in_night else day
