from datetime import datetime

from PIL import Image

from app.frame import FRAME_SIZE, compute_brightness, pack_frame


def make_image(color=(0, 0, 0)) -> Image.Image:
    return Image.new("RGB", (64, 32), color)


def test_frame_is_4104_bytes():
    assert FRAME_SIZE == 4104
    assert len(pack_frame(make_image(), brightness=180)) == 4104


def test_header_layout():
    data = pack_frame(make_image(), brightness=200)
    assert data[0:2] == b"MB"
    assert data[2] == 1  # version
    assert data[3] == 0  # flags
    assert data[4] == 200  # brightness
    assert data[5] == 64  # width
    assert data[6] == 32  # height
    assert data[7] == 0  # poll hint: 0 = client default


def test_poll_hint_defaults_to_zero():
    """0 means "use your built-in default" — what the device has always seen."""
    assert pack_frame(make_image(), brightness=200)[7] == 0
    assert pack_frame(make_image(), brightness=200, poll_ms=0)[7] == 0
    assert pack_frame(make_image(), brightness=200, poll_ms=-10)[7] == 0


def test_poll_hint_encoded_in_10ms_units():
    assert pack_frame(make_image(), brightness=0, poll_ms=50)[7] == 5
    assert pack_frame(make_image(), brightness=0, poll_ms=1000)[7] == 100


def test_poll_hint_clamped_not_wrapped():
    # 3000ms doesn't fit a single octet at 10ms units; clamp to the 2550ms ceiling
    # rather than masking, which would wrap 300 -> 44 (a 440ms poll storm).
    assert pack_frame(make_image(), brightness=0, poll_ms=3000)[7] == 255
    assert pack_frame(make_image(), brightness=0, poll_ms=999_999)[7] == 255


def test_poll_hint_never_rounds_down_into_the_default_sentinel():
    # round(5/10) == 0 would silently turn "poll every 5ms" into "use your
    # 3-second default" — the opposite of what was asked for.
    assert pack_frame(make_image(), brightness=0, poll_ms=5)[7] == 1
    assert pack_frame(make_image(), brightness=0, poll_ms=1)[7] == 1


def test_rgb565_little_endian_packing():
    # Pure red (255,0,0) -> 0xF800 -> LE bytes 00 F8
    red = pack_frame(make_image((255, 0, 0)), brightness=0)
    assert red[8:10] == bytes([0x00, 0xF8])
    # Pure green (0,255,0) -> 0x07E0 -> LE bytes E0 07
    green = pack_frame(make_image((0, 255, 0)), brightness=0)
    assert green[8:10] == bytes([0xE0, 0x07])
    # Pure blue (0,0,255) -> 0x001F -> LE bytes 1F 00
    blue = pack_frame(make_image((0, 0, 255)), brightness=0)
    assert blue[8:10] == bytes([0x1F, 0x00])
    # White -> 0xFFFF
    white = pack_frame(make_image((255, 255, 255)), brightness=0)
    assert white[8:10] == b"\xff\xff"


def test_pixel_addressing_row_major():
    img = make_image()
    img.putpixel((5, 2), (255, 255, 255))
    data = pack_frame(img, brightness=0)
    offset = 8 + 2 * (2 * 64 + 5)
    assert data[offset : offset + 2] == b"\xff\xff"
    # Everything else black
    assert data[8:10] == b"\x00\x00"


def test_brightness_clamped_not_wrapped():
    assert pack_frame(make_image(), brightness=300)[4] == 255
    assert pack_frame(make_image(), brightness=-5)[4] == 0


def test_brightness_day():
    now = datetime(2026, 7, 7, 12, 0)
    assert compute_brightness(now, day=180, night=40, night_start="22:00", night_end="06:30") == 180


def test_brightness_night_before_midnight():
    now = datetime(2026, 7, 7, 23, 15)
    assert compute_brightness(now, day=180, night=40, night_start="22:00", night_end="06:30") == 40


def test_brightness_night_after_midnight():
    now = datetime(2026, 7, 7, 3, 0)
    assert compute_brightness(now, day=180, night=40, night_start="22:00", night_end="06:30") == 40


def test_brightness_boundaries():
    kw = dict(day=180, night=40, night_start="22:00", night_end="06:30")
    assert compute_brightness(datetime(2026, 7, 7, 22, 0), **kw) == 40  # night starts
    assert compute_brightness(datetime(2026, 7, 7, 6, 30), **kw) == 180  # night ends
    assert compute_brightness(datetime(2026, 7, 7, 6, 29), **kw) == 40


def test_brightness_window_not_wrapping_midnight():
    # A window entirely inside one day, e.g. quiet afternoon 13:00-15:00
    kw = dict(day=180, night=40, night_start="13:00", night_end="15:00")
    assert compute_brightness(datetime(2026, 7, 7, 14, 0), **kw) == 40
    assert compute_brightness(datetime(2026, 7, 7, 16, 0), **kw) == 180
