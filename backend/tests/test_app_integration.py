"""App-level smoke tests: full stack with MOCK=true, no network."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


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
