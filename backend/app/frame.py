"""Binary frame format for the ESP32 client.

Layout (4104 bytes total):
  [0:2]  magic "MB"
  [2]    version (1)
  [3]    flags (bit0 = blank display; reserved)
  [4]    brightness 0-255
  [5]    width (64)
  [6]    height (32)
  [7]    poll hint: 0 = client uses its own default, else poll interval in
         units of 10ms (1..255 -> 10..2550ms)
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


MAX_POLL_HINT_MS = 2550  # 255 * 10ms — the most a single octet can express


def encode_poll_hint(poll_ms: int) -> int:
    """Header byte [7]: 0 = client default, else 10ms units.

    Rounds *up* to 1 for any positive request: round(5 / 10) == 0 would silently
    mean "use your 3-second default" — the opposite of asking to poll every 5ms.

    Requests slower than the byte can express fall back to 0 rather than
    saturating at 255. Saturating would turn "poll every 5s" into 2550ms, which
    is *faster* than the client's own 3s default — erring toward more traffic
    when the caller explicitly asked for less.
    """
    if poll_ms <= 0 or poll_ms > MAX_POLL_HINT_MS:
        return 0
    return max(1, min(255, round(poll_ms / 10)))


def pack_frame(img: Image.Image, brightness: int, flags: int = 0, poll_ms: int = 0) -> bytes:
    if img.size != (WIDTH, HEIGHT):
        raise ValueError(f"expected {WIDTH}x{HEIGHT} image, got {img.size}")
    # Clamp, don't mask: & 0xFF would turn a miswired 300 into "44" (dim) and
    # -1 into full blast at night. Same reasoning for the poll hint.
    header = bytes([MAGIC[0], MAGIC[1], VERSION, flags, max(0, min(255, brightness)),
                    WIDTH, HEIGHT, encode_poll_hint(poll_ms)])
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
