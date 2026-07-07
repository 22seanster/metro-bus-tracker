"""Open-Meteo current weather. Free, no API key."""

from dataclasses import dataclass

import httpx

from .base import Provider

URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class Weather:
    temp_f: int
    hi_f: int
    lo_f: int
    wmo_code: int


def normalize_weather(payload: dict) -> Weather:
    return Weather(
        temp_f=round(payload["current"]["temperature_2m"]),
        hi_f=round(payload["daily"]["temperature_2m_max"][0]),
        lo_f=round(payload["daily"]["temperature_2m_min"][0]),
        wmo_code=int(payload["current"]["weather_code"]),
    )


class WeatherProvider(Provider):
    name = "weather"

    def __init__(self, lat: float, lon: float, tz: str, interval: float, stale_factor: float = 2, **kw):
        super().__init__(interval=interval, stale_factor=stale_factor, **kw)
        self.params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min",
            "temperature_unit": "fahrenheit",
            "timezone": tz,
            "forecast_days": 1,
        }

    async def fetch(self) -> Weather:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(URL, params=self.params)
            r.raise_for_status()
            return normalize_weather(r.json())
