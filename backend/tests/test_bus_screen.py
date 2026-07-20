from datetime import datetime, timezone

from PIL import Image, ImageDraw

from app.providers.bus import Arrival
from app.screens.bus import BusScreen

NOW = datetime(2026, 7, 7, 9, 0, tzinfo=timezone.utc)

ROUTE_IDS = ["051", "052"]
LABELS = {"051": "51", "052": "52"}
COLORS = {"051": "#7B2FBE", "052": "#008060"}


class StubBusProvider:
    def __init__(self, arrivals, stale=False):
        self._arrivals = arrivals
        self._stale = stale

    def snapshot(self):
        return self._arrivals

    def is_stale(self):
        return self._stale


def make_screen(arrivals, stale=False):
    return BusScreen(dwell_seconds=12, provider=StubBusProvider(arrivals, stale),
                     route_ids=ROUTE_IDS, labels=LABELS, colors=COLORS)


def render(screen):
    img = Image.new("RGB", (64, 32))
    screen.render(img, ImageDraw.Draw(img), NOW)
    return img


def count_lit(img):
    return sum(1 for v in img.convert("L").tobytes() if v)


def arrivals_sample():
    return [
        Arrival("051", 4, int(NOW.timestamp()) + 240),
        Arrival("052", 9, int(NOW.timestamp()) + 540),
        Arrival("051", 18, int(NOW.timestamp()) + 1080),
    ]


def test_active_only_with_arrivals():
    assert make_screen(arrivals_sample()).is_active(NOW)
    assert not make_screen([]).is_active(NOW)
    assert not make_screen(None).is_active(NOW)


def test_renders_route_badges_in_route_colors():
    img = render(make_screen(arrivals_sample()))
    # Sample the badge fill just left of the label glyphs
    assert img.getpixel((2, 7)) == (0x7B, 0x2F, 0xBE)  # row 1 badge: route 51 purple
    assert img.getpixel((2, 23)) == (0x00, 0x80, 0x60)  # row 2 badge: route 52 green
    assert count_lit(img) > 100


def test_route_with_no_arrivals_shows_dashes():
    only_51 = [Arrival("051", 4, int(NOW.timestamp()) + 240)]
    img = render(make_screen(only_51))
    # Second row still has its badge, and some pixels right of it (the dashes)
    assert img.getpixel((2, 23)) == (0x00, 0x80, 0x60)
    right_of_badge = img.crop((16, 16, 64, 32))
    assert count_lit(right_of_badge) > 0


def test_stale_dot_when_provider_stale():
    img = render(make_screen(arrivals_sample(), stale=True))
    assert img.getpixel((61, 0)) != (0, 0, 0)


def test_no_stale_dot_when_fresh():
    img = render(make_screen(arrivals_sample(), stale=False))
    assert img.getpixel((61, 0)) == (0, 0, 0)


def test_minutes_recomputed_from_epoch_not_frozen_field():
    # The snapshot's minutes field is fetch-time state; render must ignore it
    # and derive minutes from epoch, or the display drifts between polls.
    frozen = [Arrival("051", 999, int(NOW.timestamp()) + 240)]
    fresh = [Arrival("051", 4, int(NOW.timestamp()) + 240)]
    assert render(make_screen(frozen)).tobytes() == render(make_screen(fresh)).tobytes()


def test_passed_arrivals_drop_off():
    # An arrival whose time already passed (e.g. during a METRO outage with a
    # kept-last-good snapshot) renders as dashes, same as no arrivals.
    passed = [Arrival("051", 5, int(NOW.timestamp()) - 60)]
    assert render(make_screen(passed)).tobytes() == render(make_screen([])).tobytes()
