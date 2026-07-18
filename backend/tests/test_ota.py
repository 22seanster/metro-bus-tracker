"""Firmware release module + OTA endpoints."""

import json

import pytest
from fastapi.testclient import TestClient

from app import ota
from app.config import get_settings


def _write_release(dir_path, build, sha, blob=b"\x00\x01FIRMWARE"):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "firmware.bin").write_bytes(blob)
    (dir_path / "latest.json").write_text(json.dumps({"build": build, "sha": sha}))


# --- module-level unit tests -------------------------------------------------

def test_status_absent(tmp_path):
    assert ota.firmware_status(tmp_path) == {"present": False, "build": None, "sha": None}


def test_status_present(tmp_path):
    _write_release(tmp_path, 42, "abc1234")
    assert ota.firmware_status(tmp_path) == {"present": True, "build": 42, "sha": "abc1234"}


def test_bin_path_absent(tmp_path):
    assert ota.firmware_bin_path(tmp_path) is None


def test_bin_path_present(tmp_path):
    _write_release(tmp_path, 42, "abc1234")
    assert ota.firmware_bin_path(tmp_path) == tmp_path / "firmware.bin"


# --- endpoint tests ----------------------------------------------------------

@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("MOCK", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(ota, "FIRMWARE_DIR", tmp_path)
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c, tmp_path
    get_settings.cache_clear()


def test_latest_json_404_when_absent(client):
    c, _ = client
    assert c.get("/firmware/latest.json").status_code == 404


def test_latest_json_served(client):
    c, d = client
    _write_release(d, 7, "deadbee")
    r = c.get("/firmware/latest.json")
    assert r.status_code == 200
    assert r.json() == {"build": 7, "sha": "deadbee"}


def test_firmware_bin_404_when_absent(client):
    c, _ = client
    assert c.get("/firmware.bin").status_code == 404


def test_firmware_bin_served(client):
    c, d = client
    _write_release(d, 7, "deadbee", blob=b"\x00\x01FIRMWARE")
    r = c.get("/firmware.bin")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.content == b"\x00\x01FIRMWARE"


def test_status_firmware_block_absent(client):
    c, _ = client
    assert c.get("/status").json()["firmware"] == {"present": False, "build": None, "sha": None}


def test_status_firmware_block_present(client):
    c, d = client
    _write_release(d, 99, "cafef00")
    assert c.get("/status").json()["firmware"] == {"present": True, "build": 99, "sha": "cafef00"}
