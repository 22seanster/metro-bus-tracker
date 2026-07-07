"""FastAPI app: frame endpoints for the ESP32, preview page + status for humans."""

import io
import logging

from fastapi import FastAPI, Query, Response

from .config import get_settings
from .engine import RenderEngine
from .screens.clock import ClockScreen


def build_screens(settings) -> list:
    """Ordered screen registry. The always-active clock goes last: rotation
    falls back to the final screen when nothing else is active."""
    return [
        ClockScreen(dwell_seconds=settings.clock_dwell_seconds),
    ]


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    app = FastAPI(title="Metro Bus Tracker")
    engine = RenderEngine(settings, build_screens(settings))
    app.state.engine = engine

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

    return app


app = create_app()
