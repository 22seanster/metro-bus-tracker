"""Misconfiguration must fail at startup, not at frame-render time."""

import pytest
from pydantic import ValidationError

import pytest

from app.config import Settings


# --- SPOTIFY_SCROLL kill switch ---------------------------------------------
#
# This is the emergency lever for stopping 20x/sec polling once the fast-polling
# firmware is deployed. Settings are built inside create_app(), so a
# ValidationError here takes the WHOLE backend down and crash-loops the
# container -- the panel goes to NO LINK. A fat-fingered kill switch must
# degrade to a default, never take the service offline.


@pytest.mark.parametrize("raw", ["false", "False", "FALSE", "0", "no", "off",
                                 "false ", " false", '"false"', "'false'"])
def test_kill_switch_accepts_realistic_ways_of_typing_false(raw, monkeypatch):
    monkeypatch.setenv("SPOTIFY_SCROLL", raw)
    assert Settings().spotify_scroll is False


@pytest.mark.parametrize("raw", ["true", "True", "1", "yes", "on", "true ", '"true"'])
def test_kill_switch_accepts_realistic_ways_of_typing_true(raw, monkeypatch):
    monkeypatch.setenv("SPOTIFY_SCROLL", raw)
    assert Settings().spotify_scroll is True


@pytest.mark.parametrize("raw", ["", "   ", "maybe", "2", "flase"])
def test_unparseable_kill_switch_never_takes_the_backend_down(raw, monkeypatch):
    monkeypatch.setenv("SPOTIFY_SCROLL", raw)
    assert Settings().spotify_scroll is True  # falls back to the default


def test_defaults_valid():
    Settings()


@pytest.mark.parametrize("field, value", [
    ("night_start", "10pm"),
    ("night_end", "26:00"),
    ("night_start", "22"),
    ("brightness", 300),
    ("night_brightness", -1),
    ("bus_dwell_seconds", 0),
    ("clock_dwell_seconds", -3),
])
def test_bad_values_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_valid_night_window_accepted():
    s = Settings(night_start="23:45", night_end="05:00")
    assert s.night_start == "23:45"
