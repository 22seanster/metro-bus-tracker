"""App-level smoke tests: full stack with MOCK=true, no network."""

import inspect
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config import Settings, get_settings
from app.screens.spotify import SCROLL_FRAME_MS


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MOCK", "true")
    get_settings.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as c:
        # Wait for the mock pollers' first fetch
        deadline = time.time() + 5
        while time.time() < deadline:
            s = c.get("/status").json()
            ages = [p["age_seconds"] for p in s["providers"].values()]
            if all(a is not None for a in ages):
                break
            time.sleep(0.05)
        yield c
    get_settings.cache_clear()


def test_frame_bin_valid(client):
    b = client.get("/frame.bin").content
    assert len(b) == 4104
    assert b[:3] == b"MB\x01"
    assert b[5] == 64 and b[6] == 32


def test_status_reports_mock_and_all_screens_active(client):
    s = client.get("/status").json()
    assert s["mock"] is True
    assert s["screens"] == ["bus", "weather", "spotify", "clock"]
    assert set(s["active_screens"]) == {"bus", "weather", "spotify", "clock"}
    assert s["providers"]["bus"]["mock"] is True
    assert s["providers"]["weather"]["mock"] is True
    assert s["providers"]["spotify"]["mock"] is True
    assert s["providers"]["bus"]["error"] is None


def test_frame_png_and_preview(client):
    p = client.get("/frame.png?scale=4")
    assert p.headers["content-type"] == "image/png"
    home = client.get("/")
    assert home.status_code == 200
    assert "frame.png" in home.text


def test_frame_not_blank(client):
    b = client.get("/frame.bin").content
    assert any(v != 0 for v in b[8:])


def test_default_frame_carries_no_poll_hint(client):
    """Byte [7] stays 0 unless a screen actually asks for a faster cadence, so
    bus/weather/clock never speed the device up."""
    scroll_hint = SCROLL_FRAME_MS // 10  # byte [7] is in 10ms units
    b = client.get("/frame.bin").content
    hints = {client.get("/frame.bin").content[7] for _ in range(5)}
    # 0 normally, scroll_hint only while a long Spotify line is scrolling
    assert hints <= {0, scroll_hint}
    assert b[7] in (0, scroll_hint)


def test_every_screen_accepts_the_elapsed_argument(monkeypatch):
    """The engine calls render(img, draw, now, elapsed). A screen still on the
    old 3-arg signature would raise TypeError, which engine.render() swallows —
    turning that screen silently blank instead of failing loudly. Bind the real
    call signature here so that can't ship."""
    monkeypatch.setenv("MOCK", "true")
    get_settings.cache_clear()
    from app.main import build_providers, build_screens

    settings = Settings()
    screens = build_screens(settings, build_providers(settings))
    assert screens, "registry should not be empty"

    img = Image.new("RGB", (64, 32))
    args = (img, ImageDraw.Draw(img), datetime.now(timezone.utc), 0.0)
    for screen in screens:
        inspect.signature(screen.render).bind(*args)
    get_settings.cache_clear()
