from datetime import datetime, timezone

from PIL import Image, ImageDraw

from app.providers.spotify import NowPlaying
from app.screens.spotify import SpotifyScreen

NOW = datetime(2026, 7, 7, 20, 0, tzinfo=timezone.utc)


class Stub:
    def __init__(self, np):
        self._np = np

    def snapshot(self):
        return self._np

    def is_stale(self):
        return False


LONG_TRACK = "Supercalifragilistic Expialidocious Extended Anniversary Mix"
LONG_ARTIST = "Julie Andrews and the Extremely Long Ensemble Name"


def make_np(art=True, track="Texas Sun", artists="Khruangbin, Leon Bridges"):
    img = Image.new("RGB", (16, 16), (200, 60, 20)) if art else None
    return NowPlaying(account="sean", track=track, artists=artists,
                      art_url="u", device_name="Kitchen", is_playing=True, art=img)


def count_lit(img):
    return sum(1 for v in img.convert("L").tobytes() if v)


def screen(np):
    return SpotifyScreen(dwell_seconds=15, provider=Stub(np))


def render(np, elapsed=0.0):
    img = Image.new("RGB", (64, 32))
    screen(np).render(img, ImageDraw.Draw(img), NOW, elapsed)
    return img


def test_active_only_when_playing():
    assert SpotifyScreen(dwell_seconds=10, provider=Stub(make_np())).is_active(NOW)
    assert not SpotifyScreen(dwell_seconds=10, provider=Stub(None)).is_active(NOW)


def test_renders_album_art_block():
    img = render(make_np())
    assert img.getpixel((6, 15)) == (200, 60, 20)  # inside the 16x16 art area
    assert count_lit(img) > 200


def test_renders_without_art():
    img = render(make_np(art=False))
    assert count_lit(img) > 30  # text still drawn


# --- scrolling ---------------------------------------------------------------


def test_long_track_scrolls_over_time():
    np = make_np(track=LONG_TRACK)
    early = render(np, elapsed=2.0)
    later = render(np, elapsed=4.0)
    assert early.tobytes() != later.tobytes()


def test_short_text_never_moves():
    np = make_np(track="Texas Sun", artists="Khruangbin")
    assert render(np, elapsed=0.0).tobytes() == render(np, elapsed=7.0).tobytes()


def test_scroll_holds_briefly_before_moving():
    """Without the hold, the first character is already sliding off before the
    eye lands on the screen."""
    np = make_np(track=LONG_TRACK)
    assert render(np, elapsed=0.0).tobytes() == render(np, elapsed=0.9).tobytes()
    assert render(np, elapsed=0.0).tobytes() != render(np, elapsed=2.0).tobytes()


def test_long_artist_scrolls_too():
    np = make_np(track="Short", artists=LONG_ARTIST)
    assert render(np, elapsed=2.0).tobytes() != render(np, elapsed=4.0).tobytes()


def test_scrolling_text_never_touches_the_album_art():
    """The art sits at x=3..18 and the text window starts at x=22. PIL clips at
    the image edge, not at the window, so this guards the bleed."""
    art = Image.new("RGB", (16, 16), (200, 60, 20))
    np = NowPlaying(account="sean", track=LONG_TRACK, artists=LONG_ARTIST,
                    art_url="u", device_name="Kitchen", is_playing=True, art=art)
    for elapsed in (0.0, 1.5, 3.0, 6.0, 11.0):
        img = render(np, elapsed=elapsed)
        assert img.crop((3, 8, 19, 24)).tobytes() == art.tobytes(), f"art damaged at {elapsed}"
        for x in range(0, 22):
            for y in range(0, 32):
                if 3 <= x < 19 and 8 <= y < 24:
                    continue  # the art itself
                assert img.getpixel((x, y)) == (0, 0, 0), f"bled to x={x} at {elapsed}"


# --- cadence hint ------------------------------------------------------------


def test_hint_requests_a_fast_cadence_only_while_scrolling():
    assert screen(make_np(track=LONG_TRACK)).frame_interval_ms(NOW) == 50
    assert screen(make_np(track="Short", artists=LONG_ARTIST)).frame_interval_ms(NOW) == 50


def test_hint_is_zero_when_nothing_overflows():
    """0 = no preference, so the device stays on its 3s default and short tracks
    cost no extra WiFi traffic."""
    assert screen(make_np(track="Texas Sun", artists="Khruangbin")).frame_interval_ms(NOW) == 0


def test_hint_is_zero_when_nothing_is_playing():
    assert screen(None).frame_interval_ms(NOW) == 0
