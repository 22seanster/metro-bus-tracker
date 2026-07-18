"""FastAPI app: frame endpoints for the ESP32, preview page + status for humans."""

import asyncio
import io
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse

from .config import Settings, get_settings
from .engine import RenderEngine
from . import ota
from .providers.base import Provider
from .providers.bus import BusProvider
from .providers.mock import MockBusProvider, MockSpotifyProvider, MockWeatherProvider
from .providers.spotify import SpotifyProvider
from .providers.weather import WeatherProvider
from .screens.bus import BusScreen
from .screens.clock import ClockScreen
from .screens.spotify import SpotifyScreen
from .screens.weather import WeatherScreen

log = logging.getLogger(__name__)


def build_providers(settings: Settings) -> dict[str, Provider]:
    if settings.mock or not settings.metro_api_key:
        if not settings.mock:
            log.warning(
                "METRO_API_KEY is not set - bus arrivals are MOCK data. "
                "Get a free key at https://api-portal.ridemetro.org/ and set METRO_API_KEY."
            )
        bus = MockBusProvider(route_ids=settings.route_id_list)
    else:
        bus = BusProvider(
            url=settings.gtfs_rt_url,
            api_key=settings.metro_api_key,
            stop_id=settings.stop_id,
            route_ids=settings.route_id_list,
            direction_id=settings.direction_id,
            lookahead_minutes=settings.bus_lookahead_minutes,
            interval=settings.bus_poll_seconds,
        )
    if settings.mock:
        weather = MockWeatherProvider()
    else:
        weather = WeatherProvider(
            lat=settings.weather_lat,
            lon=settings.weather_lon,
            tz=settings.app_tz,
            interval=settings.weather_poll_seconds,
        )
    providers: dict[str, Provider] = {"bus": bus, "weather": weather}

    if settings.mock:
        providers["spotify"] = MockSpotifyProvider()
    elif settings.spotify_client_id and settings.spotify_client_secret and settings.spotify_token_map:
        providers["spotify"] = SpotifyProvider(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            refresh_tokens=settings.spotify_token_map,
            device_allowlist=settings.spotify_allowlist,
            interval=settings.spotify_poll_seconds,
        )
    return providers


def build_screens(settings: Settings, providers: dict[str, Provider]) -> list:
    """Ordered screen registry. The always-active clock goes last: rotation
    falls back to the final screen when nothing else is active.
    Additional screens slot in here."""
    screens = [
        BusScreen(
            dwell_seconds=settings.bus_dwell_seconds,
            provider=providers["bus"],
            route_ids=settings.route_id_list,
            labels=settings.route_label_map,
            colors=settings.route_color_map,
        ),
        WeatherScreen(dwell_seconds=settings.weather_dwell_seconds, provider=providers["weather"]),
    ]
    if "spotify" in providers:
        screens.append(SpotifyScreen(dwell_seconds=settings.spotify_dwell_seconds,
                                     provider=providers["spotify"]))
    screens.append(ClockScreen(dwell_seconds=settings.clock_dwell_seconds))
    return screens


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    providers = build_providers(settings)
    engine = RenderEngine(settings, build_screens(settings, providers))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks = [asyncio.create_task(p.run(), name=f"poll-{name}") for name, p in providers.items()]
        yield
        for t in tasks:
            t.cancel()

    app = FastAPI(title="Metro Bus Tracker", lifespan=lifespan)
    app.state.engine = engine
    app.state.providers = providers

    @app.get("/healthz")
    def healthz() -> str:
        return "ok"

    @app.get("/frame.bin")
    def frame_bin() -> Response:
        return Response(content=engine.frame_bytes(), media_type="application/octet-stream")

    @app.get("/firmware/latest.json")
    def firmware_latest() -> dict:
        info = ota.firmware_status(ota.FIRMWARE_DIR)
        if not info["present"]:
            raise HTTPException(status_code=404, detail="no firmware bundled")
        return {"build": info["build"], "sha": info["sha"]}

    @app.get("/firmware.bin")
    def firmware_bin_download() -> FileResponse:
        path = ota.firmware_bin_path(ota.FIRMWARE_DIR)
        if path is None:
            raise HTTPException(status_code=404, detail="no firmware bundled")
        return FileResponse(path, media_type="application/octet-stream",
                            filename="firmware.bin")

    @app.get("/frame.png")
    def frame_png(scale: int = Query(default=8, ge=1, le=16)) -> Response:
        img, _ = engine.render()
        if scale > 1:
            img = img.resize((64 * scale, 32 * scale), resample=0)  # nearest
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "no-store"})

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (Path(__file__).parent / "preview" / "index.html").read_text(encoding="utf-8")

    @app.get("/status")
    def status() -> dict:
        img, brightness = engine.render()
        return {
            "current_screen": engine.current_screen_name(),
            "screens": [s.name for s in engine.screens],
            "active_screens": [s.name for s in engine.screens if s.is_active(engine.now())],
            "brightness": brightness,
            "mock": settings.mock,
            "firmware": ota.firmware_status(ota.FIRMWARE_DIR),
            "providers": {name: p.status() for name, p in providers.items()},
        }

    return app


app = create_app()
