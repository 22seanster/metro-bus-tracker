"""Application settings. Every knob is an environment variable with a default
that matches Sean's stop: #3216 Lorraine St @ Cochran St, inbound to Downtown TC,
routes 051/052."""

import logging
from datetime import time
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Houston METRO GTFS-Realtime
    metro_api_key: str = ""
    gtfs_rt_url: str = "https://api.ridemetro.org/GtfsRealtime/TripUpdates"
    mock: bool = False

    stop_id: str = "3216"
    direction_id: int = 1
    route_ids: str = "051,052"
    route_labels: str = ""  # empty -> derived by stripping leading zeros
    route_colors: str = "#7B2FBE,#008060"

    bus_poll_seconds: float = 45
    bus_lookahead_minutes: int = 90

    # Weather (Open-Meteo, no key). Defaults to the stop's coordinates.
    weather_lat: float = 29.778398
    weather_lon: float = -95.354986
    weather_poll_seconds: float = 900

    app_tz: str = "America/Chicago"

    # Screen rotation dwell times (seconds). ge=1: an all-zero cycle would be a
    # ZeroDivisionError on every frame render, so reject it at startup instead.
    bus_dwell_seconds: int = Field(default=12, ge=1)
    weather_dwell_seconds: int = Field(default=8, ge=1)
    clock_dwell_seconds: int = Field(default=8, ge=1)

    # Panel brightness (0-255) and night dimming window (local HH:MM)
    brightness: int = Field(default=180, ge=0, le=255)
    night_brightness: int = Field(default=40, ge=0, le=255)
    night_start: str = "22:00"
    night_end: str = "06:30"

    # Spotify now-playing (optional; screen is registered only when configured).
    # One shared developer app; refresh tokens minted via scripts/spotify_auth.py.
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_refresh_tokens: str = ""  # "sean:<token>,wife:<token>" - order = priority
    spotify_device_allowlist: str = ""  # "Kitchen Speaker,Living Room TV"; empty = any device
    spotify_poll_seconds: float = 30
    # 15s so a worst-case ~60-char track completes a full scroll loop (~13.6s at
    # 20px/sec plus the 1s hold) before the screen rotates away.
    spotify_dwell_seconds: int = Field(default=15, ge=1)
    # Kill switch. Scrolling makes the device poll ~20x/sec while the Spotify
    # screen is up; set false to stop that instantly from Portainer without a
    # rebuild or an OTA. Text then freezes showing the head of each line.
    spotify_scroll: bool = True

    log_level: str = "INFO"

    @field_validator("spotify_scroll", mode="before")
    @classmethod
    def _lenient_bool(cls, v):
        """Never let a mistyped kill switch take the backend down.

        Settings are built inside create_app(), so a ValidationError here stops
        /frame.bin entirely and crash-loops the container — the panel goes to
        NO LINK. That is a catastrophic failure mode for the one lever meant to
        *recover* from trouble, and Portainer's env editor is a plain text box
        where trailing spaces and stray quotes are exactly what gets pasted.
        """
        if not isinstance(v, str):
            return v
        s = v.strip().strip('"').strip("'").strip().lower()
        if s in {"false", "0", "no", "off", "n", "f"}:
            return False
        if s in {"true", "1", "yes", "on", "y", "t"}:
            return True
        if s:
            log.warning("SPOTIFY_SCROLL=%r not understood; leaving scrolling enabled", v)
        return True

    @field_validator("night_start", "night_end")
    @classmethod
    def _validate_hhmm(cls, v: str) -> str:
        # The night window is parsed on every frame render; a malformed value
        # must fail here at startup, not turn every /frame.bin into a 500.
        h, m = v.split(":")
        time(int(h), int(m))
        return v

    @property
    def route_id_list(self) -> list[str]:
        return [r.strip() for r in self.route_ids.split(",") if r.strip()]

    @property
    def route_label_map(self) -> dict[str, str]:
        ids = self.route_id_list
        if self.route_labels.strip():
            labels = [l.strip() for l in self.route_labels.split(",")]
        else:
            labels = [r.lstrip("0") or "0" for r in ids]
        return dict(zip(ids, labels))

    @property
    def spotify_token_map(self) -> dict[str, str]:
        """'sean:tok,wife:tok' -> ordered {account: refresh_token}."""
        tokens = {}
        for pair in self.spotify_refresh_tokens.split(","):
            if ":" in pair:
                name, token = pair.split(":", 1)
                if name.strip() and token.strip():
                    tokens[name.strip()] = token.strip()
        return tokens

    @property
    def spotify_allowlist(self) -> list[str]:
        return [d.strip() for d in self.spotify_device_allowlist.split(",") if d.strip()]

    @property
    def route_color_map(self) -> dict[str, str]:
        ids = self.route_id_list
        colors = [c.strip() for c in self.route_colors.split(",") if c.strip()]
        # Cycle colors if fewer than routes
        return {r: colors[i % len(colors)] for i, r in enumerate(ids)} if colors else {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
