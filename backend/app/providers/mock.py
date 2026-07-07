"""Mock providers: plausible data with no API key or network.

Used when MOCK=true (demo/dev) and as the automatic bus fallback while
METRO_API_KEY is unset. Values derive from the wall clock, so arrivals
genuinely count down and refresh like the real thing.
"""

from .base import Provider
from .bus import Arrival, ArrivalStatusMixin
from .weather import Weather


class MockBusProvider(ArrivalStatusMixin, Provider):
    name = "bus"
    is_mock = True

    def __init__(self, route_ids: list[str], interval: float = 30, **kw):
        super().__init__(interval=interval, stale_factor=3, **kw)
        self.route_ids = route_ids

    async def fetch(self) -> list[Arrival]:
        now = self.clock()
        arrivals = []
        for i, route_id in enumerate(self.route_ids):
            period = (11 + 4 * i) * 60  # route cadences: 11 min, 15 min, ...
            phase = i * 300  # stagger routes
            until_next = period - ((now + phase) % period)
            for k in range(2):
                t = now + until_next + k * period
                arrivals.append(Arrival(route_id=route_id, minutes=int((t - now) / 60), epoch=int(t)))
        return sorted(arrivals, key=lambda a: a.epoch)


class MockWeatherProvider(Provider):
    name = "weather"
    is_mock = True

    def __init__(self, interval: float = 60, **kw):
        super().__init__(interval=interval, stale_factor=3, **kw)

    async def fetch(self) -> Weather:
        # Houston-in-July temperature curve that drifts through the day
        hour = (self.clock() % 86400) / 3600
        temp = 78 + round(14 * max(0.0, 1 - abs(hour - 15) / 9))
        codes = [0, 1, 2, 3, 61, 95]
        code = codes[int(self.clock() / 300) % len(codes)]  # new condition every 5 min
        return Weather(temp_f=temp, hi_f=95, lo_f=78, wmo_code=code)
