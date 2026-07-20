"""List the Spotify devices currently visible to each configured account.

Two uses:
  1. Pick names for SPOTIFY_DEVICE_ALLOWLIST (substring match on the *playing*
     device's name).
  2. Test presence gating: Spotify's device list is account-scoped, not
     caller-scoped, so running this from anywhere shows the same list. Run it
     with your phone on home WiFi, then again with your phone on cell data. A
     LAN-discovered device (e.g. a Google Cast target) should disappear in the
     second run; a cloud-registered one (Sonos, Echo) will not.

Reads credentials from the git-ignored .env at the repo root. Prints no secrets.

Usage:
    python scripts/spotify_devices.py
"""

import base64
import json
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime

ENV_PATH = pathlib.Path(__file__).resolve().parent.parent / ".env"
TOKEN_URL = "https://accounts.spotify.com/api/token"
DEVICES_URL = "https://api.spotify.com/v1/me/player/devices"


def load_env(path: pathlib.Path) -> dict[str, str]:
    if not path.exists():
        raise SystemExit(f"No .env at {path}")
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip("'\"")
    return env


def access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        TOKEN_URL, data=data,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)["access_token"]


def devices(token: str) -> list[dict]:
    req = urllib.request.Request(DEVICES_URL, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp).get("devices", [])


def main() -> None:
    env = load_env(ENV_PATH)
    client_id = env.get("SPOTIFY_CLIENT_ID", "")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise SystemExit("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET missing from .env")

    pairs = [p for p in env.get("SPOTIFY_REFRESH_TOKENS", "").split(",") if ":" in p]
    if not pairs:
        raise SystemExit("SPOTIFY_REFRESH_TOKENS missing or malformed in .env")

    print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S}\n")
    for pair in pairs:
        account, refresh = pair.split(":", 1)
        account = account.strip()
        try:
            found = devices(access_token(client_id, client_secret, refresh.strip()))
        except Exception as exc:  # one bad account shouldn't hide the other
            print(f"{account}: ERROR {exc}\n")
            continue

        if not found:
            print(f"{account}: no visible devices\n")
            continue
        print(f"{account}: {len(found)} visible device(s)")
        for d in found:
            mark = " <- currently playing" if d.get("is_active") else ""
            print(f"    {d.get('name', '?')!r}  [{d.get('type', '?')}]{mark}")
        print()


if __name__ == "__main__":
    main()
