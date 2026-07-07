"""Spotify now-playing across multiple accounts (e.g. Sean + wife).

Auth model: one shared Spotify developer app (client id + secret). Each account
runs scripts/spotify_auth.py once to mint a long-lived refresh token; tokens go
in SPOTIFY_REFRESH_TOKENS as "name:token,name:token" (priority = config order).

"At home" detection: Spotify's /me/player reports the playing device's name.
SPOTIFY_DEVICE_ALLOWLIST (comma-separated, case-insensitive substring match)
limits the screen to home devices; empty allows any device.
"""

import io
import time
from dataclasses import dataclass

import httpx
from PIL import Image

from .base import Provider

TOKEN_URL = "https://accounts.spotify.com/api/token"
PLAYER_URL = "https://api.spotify.com/v1/me/player"
ART_SIZE = 16


@dataclass
class NowPlaying:
    account: str
    track: str
    artists: str
    art_url: str | None
    device_name: str
    is_playing: bool
    art: Image.Image | None = None


def normalize_playback(account: str, payload: dict | None) -> NowPlaying | None:
    if not payload or not payload.get("is_playing") or not payload.get("item"):
        return None
    item = payload["item"]
    images = item.get("album", {}).get("images", [])
    smallest = min(images, key=lambda i: i.get("width") or 10_000)["url"] if images else None
    return NowPlaying(
        account=account,
        track=item.get("name", "?"),
        artists=", ".join(a["name"] for a in item.get("artists", [])),
        art_url=smallest,
        device_name=payload.get("device", {}).get("name", ""),
        is_playing=True,
    )


def device_allowed(device_name: str, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    name = device_name.lower()
    return any(allowed.strip().lower() in name for allowed in allowlist if allowed.strip())


def select_playing(order: list[str], states: dict[str, NowPlaying | None],
                   allowlist: list[str]) -> NowPlaying | None:
    for account in order:
        np = states.get(account)
        if np and np.is_playing and device_allowed(np.device_name, allowlist):
            return np
    return None


class SpotifyProvider(Provider):
    name = "spotify"

    def __init__(self, client_id: str, client_secret: str, refresh_tokens: dict[str, str],
                 device_allowlist: list[str], interval: float, **kw):
        super().__init__(interval=interval, stale_factor=3, **kw)
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_tokens = refresh_tokens  # account -> refresh token (insertion order = priority)
        self.device_allowlist = device_allowlist
        self._access: dict[str, tuple[str, float]] = {}  # account -> (token, expiry epoch)
        self._art_cache: tuple[str, Image.Image] | None = None

    async def _access_token(self, client: httpx.AsyncClient, account: str) -> str:
        cached = self._access.get(account)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        r = await client.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_tokens[account],
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })
        r.raise_for_status()
        payload = r.json()
        token = payload["access_token"]
        self._access[account] = (token, time.time() + payload.get("expires_in", 3600))
        return token

    async def _playback(self, client: httpx.AsyncClient, account: str) -> NowPlaying | None:
        token = await self._access_token(client, account)
        r = await client.get(PLAYER_URL, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 204:  # nothing playing
            return None
        r.raise_for_status()
        return normalize_playback(account, r.json())

    async def _attach_art(self, client: httpx.AsyncClient, np: NowPlaying) -> None:
        if not np.art_url:
            return
        if self._art_cache and self._art_cache[0] == np.art_url:
            np.art = self._art_cache[1]
            return
        r = await client.get(np.art_url)
        r.raise_for_status()
        art = Image.open(io.BytesIO(r.content)).convert("RGB").resize((ART_SIZE, ART_SIZE))
        self._art_cache = (np.art_url, art)
        np.art = art

    async def fetch(self) -> NowPlaying | None:
        async with httpx.AsyncClient(timeout=10) as client:
            states: dict[str, NowPlaying | None] = {}
            for account in self.refresh_tokens:
                try:
                    states[account] = await self._playback(client, account)
                except Exception:  # one broken account must not blank the other
                    states[account] = None
            np = select_playing(list(self.refresh_tokens), states, self.device_allowlist)
            if np:
                await self._attach_art(client, np)
            return np
