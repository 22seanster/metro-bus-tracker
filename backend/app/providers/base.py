"""Base class for background data pollers (bus, weather, later Spotify).

Each provider runs an asyncio loop: fetch -> store snapshot -> sleep. Errors
keep the last good data (screens show a stale indicator instead of crashing)
and back off exponentially, capped at the normal poll interval.
"""

import asyncio
import logging
import re
import time
from typing import Any, Callable

log = logging.getLogger(__name__)

BACKOFF_BASE_SECONDS = 5

# Exception messages can embed full request URLs (httpx does), and URLs can
# carry secrets in their query string. last_error is served on /status and
# logged, so strip query strings before the message leaves this module.
_URL_QUERY_RE = re.compile(r"\?[^\s'\"]+")


class Provider:
    name: str = "provider"
    is_mock: bool = False

    def __init__(self, interval: float, stale_factor: float = 3, clock: Callable[[], float] = time.time):
        self.interval = interval
        self.stale_factor = stale_factor
        self.clock = clock
        self._data: Any | None = None
        self.fetched_at: float | None = None
        self.last_error: str | None = None
        self.error_count = 0

    async def fetch(self) -> Any:
        raise NotImplementedError

    def snapshot(self) -> Any | None:
        return self._data

    def age_seconds(self) -> float | None:
        if self.fetched_at is None:
            return None
        return self.clock() - self.fetched_at

    def is_stale(self) -> bool:
        age = self.age_seconds()
        return age is None or age > self.stale_factor * self.interval

    def next_delay(self) -> float:
        if self.error_count:
            return min(self.interval, BACKOFF_BASE_SECONDS * 2**self.error_count)
        return self.interval

    async def refresh_once(self) -> None:
        try:
            self._data = await self.fetch()
            self.fetched_at = self.clock()
            self.last_error = None
            self.error_count = 0
        except Exception as e:  # noqa: BLE001 - any fetch failure must not kill the loop
            self.error_count += 1
            self.last_error = _URL_QUERY_RE.sub("?<query-redacted>", f"{type(e).__name__}: {e}")
            log.warning("%s fetch failed (attempt %d): %s", self.name, self.error_count, self.last_error)

    async def run(self) -> None:
        while True:
            await self.refresh_once()
            await asyncio.sleep(self.next_delay())

    def status(self) -> dict:
        age = self.age_seconds()
        return {
            "age_seconds": round(age, 1) if age is not None else None,
            "stale": self.is_stale(),
            "error": self.last_error,
            "error_count": self.error_count,
            "mock": self.is_mock,
        }
