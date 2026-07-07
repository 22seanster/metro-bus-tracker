"""Application settings. Every knob is an environment variable with a default
that matches Sean's stop: #3216 Lorraine St @ Cochran St, inbound to Downtown TC,
routes 051/052."""

from functools import lru_cache

from pydantic_settings import BaseSettings


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

    # Screen rotation dwell times (seconds)
    bus_dwell_seconds: int = 12
    weather_dwell_seconds: int = 8
    clock_dwell_seconds: int = 8

    # Panel brightness (0-255) and night dimming window (local HH:MM)
    brightness: int = 180
    night_brightness: int = 40
    night_start: str = "22:00"
    night_end: str = "06:30"

    log_level: str = "INFO"

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
    def route_color_map(self) -> dict[str, str]:
        ids = self.route_id_list
        colors = [c.strip() for c in self.route_colors.split(",") if c.strip()]
        # Cycle colors if fewer than routes
        return {r: colors[i % len(colors)] for i, r in enumerate(ids)} if colors else {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
