from app.providers.bus import Arrival, BusProvider
from app.providers.mock import MockBusProvider


def test_bus_provider_status_includes_arrivals():
    p = BusProvider(url="http://x", api_key="k", stop_id="3216", route_ids=["051", "052"],
                    direction_id=1, lookahead_minutes=90, interval=45)
    p._data = [Arrival("051", 4, 1000), Arrival("052", 9, 1300)]
    s = p.status()
    assert s["arrivals"] == [
        {"route": "051", "minutes": 4},
        {"route": "052", "minutes": 9},
    ]


async def test_mock_bus_provider_status_includes_arrivals():
    p = MockBusProvider(route_ids=["051"])
    await p.refresh_once()
    s = p.status()
    assert s["arrivals"], "mock provider should always report upcoming arrivals"
    assert all(set(a) == {"route", "minutes"} for a in s["arrivals"])
