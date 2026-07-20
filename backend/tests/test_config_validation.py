"""Misconfiguration must fail at startup, not at frame-render time."""

import pytest
from pydantic import ValidationError

from app.config import Settings


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
