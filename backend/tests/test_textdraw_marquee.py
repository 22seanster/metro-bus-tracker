"""draw_marquee: scrolling text clipped to a window.

The clipping tests are the important ones. PIL clips at *image* bounds, not at
the caller's region, so a naive negative-x draw.text would bleed left over the
Spotify album art at x=3..18.
"""

from PIL import Image, ImageDraw

from app import fonts
from app.textdraw import draw_marquee, text_width

WHITE = (255, 255, 255)
SHORT = "Queen"
LONG = "Bohemian Rhapsody Remastered"
WINDOW = 41
GAP = 12


def tiny():
    return fonts.tiny()


def blank() -> Image.Image:
    return Image.new("RGB", (64, 32))


def marquee_at(offset: int, text: str = LONG, xy=(22, 11), width=WINDOW) -> Image.Image:
    img = blank()
    draw_marquee(img, xy, text, tiny(), WHITE, width, offset=offset, gap=GAP)
    return img


def test_text_that_fits_is_pixel_identical_to_a_plain_draw():
    """Short track names must look exactly as they do today — no regression for
    the common case, and no branching needed in the calling screen."""
    expected = blank()
    ImageDraw.Draw(expected).text((22, 11), SHORT, font=tiny(), fill=WHITE)

    got = blank()
    draw_marquee(got, (22, 11), SHORT, tiny(), WHITE, WINDOW, offset=0, gap=GAP)

    assert got.tobytes() == expected.tobytes()


def test_text_that_fits_ignores_the_offset():
    assert marquee_at(0, text=SHORT).tobytes() == marquee_at(37, text=SHORT).tobytes()


def test_offset_zero_shows_the_head_of_the_string():
    """At offset 0 the window is just the plain text clipped to the window."""
    reference = blank()
    ImageDraw.Draw(reference).text((22, 11), LONG, font=tiny(), fill=WHITE)
    reference = reference.crop((22, 0, 22 + WINDOW, 32))

    got = marquee_at(0).crop((22, 0, 22 + WINDOW, 32))

    assert got.tobytes() == reference.tobytes()


def test_scrolling_matches_an_infinite_tape_of_text_and_gap():
    """The window at offset N must equal the Nth window of a tape built by
    repeating "text + gap". This pins down both the scroll direction and the
    placement of the wrapped copy."""
    period = text_width(LONG, tiny()) + GAP
    tape = Image.new("RGB", (2 * period + WINDOW, 32))
    d = ImageDraw.Draw(tape)
    for stamp in (0, period, 2 * period):
        d.text((stamp, 11), LONG, font=tiny(), fill=WHITE)

    for offset in (0, 1, 7, 40, period // 2, period - 1):
        expected = tape.crop((offset, 0, offset + WINDOW, 32))
        got = marquee_at(offset).crop((22, 0, 22 + WINDOW, 32))
        assert got.tobytes() == expected.tobytes(), f"mismatch at offset {offset}"


def test_offset_wraps_modulo_the_period():
    period = text_width(LONG, tiny()) + GAP
    assert marquee_at(0).tobytes() == marquee_at(period).tobytes()
    assert marquee_at(5).tobytes() == marquee_at(period + 5).tobytes()
    assert marquee_at(5).tobytes() == marquee_at(5 * period + 5).tobytes()


def test_never_draws_outside_the_window():
    """Regression guard for the album art at x=3..18: nothing may be drawn left
    of the window start or right of its end, at any offset."""
    period = text_width(LONG, tiny()) + GAP
    for offset in (0, 3, 19, period - 1, period // 3):
        img = Image.new("RGB", (64, 32), (7, 7, 7))  # non-black canvas
        draw_marquee(img, (22, 11), LONG, tiny(), WHITE, WINDOW, offset=offset, gap=GAP)
        for x in range(64):
            if 22 <= x < 22 + WINDOW:
                continue
            for y in range(32):
                assert img.getpixel((x, y)) == (7, 7, 7), f"bled at x={x} offset={offset}"


def test_empty_text_is_a_noop():
    img = Image.new("RGB", (64, 32), (7, 7, 7))
    draw_marquee(img, (22, 11), "", tiny(), WHITE, WINDOW, offset=3, gap=GAP)
    assert img.tobytes() == Image.new("RGB", (64, 32), (7, 7, 7)).tobytes()
