"""FastAPI app: frame endpoints for the ESP32, preview page + status for humans."""

import logging

from fastapi import FastAPI

from .config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    app = FastAPI(title="Metro Bus Tracker")

    @app.get("/healthz")
    def healthz() -> str:
        return "ok"

    return app


app = create_app()
