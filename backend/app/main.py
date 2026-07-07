"""FastAPI app: frame endpoints for the ESP32, preview page + status for humans."""

import asyncio
import io
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Response
from fastapi.responses import HTMLResponse

from .config import Settings, get_settings
from .engine import RenderEngine
from .providers.base import Provider
from .providers.weather import WeatherProvider
from .screens.clock import ClockScreen
from .screens.weather import WeatherScreen


def build_providers(settings: Settings) -> dict[str, Provider]:
    return {
        "weather": WeatherProvider(
            lat=settings.weather_lat,
            lon=settings.weather_lon,
            tz=settings.app_tz,
            interval=settings.weather_poll_seconds,
        ),
    }


def build_screens(settings: Settings, providers: dict[str, Provider]) -> list:
    """Ordered screen registry. The always-active clock goes last: rotation
    falls back to the final screen when nothing else is active."""
    return [
        WeatherScreen(dwell_seconds=settings.weather_dwell_seconds, provider=providers["weather"]),
        ClockScreen(dwell_seconds=settings.clock_dwell_seconds),
    ]


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
            "providers": {name: p.status() for name, p in providers.items()},
        }

    return app


app = create_app()
