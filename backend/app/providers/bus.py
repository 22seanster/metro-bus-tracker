"""Houston METRO GTFS-Realtime TripUpdates: next arrivals at one stop."""

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from google.transit import gtfs_realtime_pb2 as rt

from .base import Provider


@dataclass(frozen=True)
class Arrival:
    route_id: str
    minutes: int
    epoch: int


def parse_trip_updates(
    feed_bytes: bytes,
    *,
    stop_id: str,
    route_ids: list[str],
    direction_id: int,
    now: datetime,
    lookahead_minutes: int,
) -> list[Arrival]:
    feed = rt.FeedMessage()
    feed.ParseFromString(feed_bytes)
    now_epoch = now.timestamp()
    arrivals: list[Arrival] = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        trip = entity.trip_update.trip
        if trip.route_id not in route_ids:
            continue
        # If the feed omits direction_id, be permissive rather than show nothing.
        if trip.HasField("direction_id") and trip.direction_id != direction_id:
            continue
        for stu in entity.trip_update.stop_time_update:
            if stu.stop_id != stop_id:
                continue
            if stu.HasField("arrival") and stu.arrival.time:
                t = stu.arrival.time
            elif stu.HasField("departure") and stu.departure.time:
                t = stu.departure.time
            else:
                continue
            minutes = (t - now_epoch) / 60
            if minutes < 0 or minutes > lookahead_minutes:
                continue
            arrivals.append(Arrival(route_id=trip.route_id, minutes=int(minutes), epoch=int(t)))
    return sorted(arrivals, key=lambda a: a.epoch)


class ArrivalStatusMixin:
    """Adds the upcoming arrivals to /status for easy eyeball verification."""

    def status(self) -> dict:
        s = super().status()
        s["arrivals"] = [
            {"route": a.route_id, "minutes": a.minutes} for a in (self.snapshot() or [])
        ]
        return s


class BusProvider(ArrivalStatusMixin, Provider):
    name = "bus"

    def __init__(self, url: str, api_key: str, stop_id: str, route_ids: list[str],
                 direction_id: int, lookahead_minutes: int, interval: float, **kw):
        super().__init__(interval=interval, stale_factor=3, **kw)
        self.url = url
        self.api_key = api_key
        self.stop_id = stop_id
        self.route_ids = route_ids
        self.direction_id = direction_id
        self.lookahead_minutes = lookahead_minutes

    async def fetch(self) -> list[Arrival]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(self.url, params={"subscription-key": self.api_key})
            r.raise_for_status()
            return parse_trip_updates(
                r.content,
                stop_id=self.stop_id,
                route_ids=self.route_ids,
                direction_id=self.direction_id,
                now=datetime.now(timezone.utc),
                lookahead_minutes=self.lookahead_minutes,
            )
