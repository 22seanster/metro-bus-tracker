from datetime import datetime, timezone

from google.transit import gtfs_realtime_pb2 as rt

from app.providers.bus import parse_trip_updates

NOW = datetime(2026, 7, 7, 9, 0, 0, tzinfo=timezone.utc)
NOW_EPOCH = int(NOW.timestamp())

STOP = "3216"
ROUTES = ["051", "052"]
DIRECTION = 1


def build_feed(*trips) -> bytes:
    """trips: (route_id, direction_id | None, [(stop_id, arrival_epoch | None, departure_epoch | None), ...])"""
    feed = rt.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = NOW_EPOCH
    for i, (route_id, direction_id, stops) in enumerate(trips):
        e = feed.entity.add()
        e.id = f"e{i}"
        tu = e.trip_update
        tu.trip.trip_id = f"t{i}"
        tu.trip.route_id = route_id
        if direction_id is not None:
            tu.trip.direction_id = direction_id
        for stop_id, arr, dep in stops:
            stu = tu.stop_time_update.add()
            stu.stop_id = stop_id
            if arr is not None:
                stu.arrival.time = arr
            if dep is not None:
                stu.departure.time = dep
    return feed.SerializeToString()


def minutes_of(arrivals):
    return [(a.route_id, a.minutes) for a in arrivals]


def parse(feed_bytes, lookahead=90):
    return parse_trip_updates(feed_bytes, stop_id=STOP, route_ids=ROUTES,
                              direction_id=DIRECTION, now=NOW, lookahead_minutes=lookahead)


def test_matching_trip_included():
    feed = build_feed(("051", 1, [(STOP, NOW_EPOCH + 300, None)]))
    assert minutes_of(parse(feed)) == [("051", 5)]


def test_wrong_route_excluded():
    feed = build_feed(("009", 1, [(STOP, NOW_EPOCH + 300, None)]))
    assert parse(feed) == []


def test_wrong_stop_excluded():
    feed = build_feed(("051", 1, [("9999", NOW_EPOCH + 300, None)]))
    assert parse(feed) == []


def test_wrong_direction_excluded():
    feed = build_feed(("051", 0, [(STOP, NOW_EPOCH + 300, None)]))
    assert parse(feed) == []


def test_unset_direction_included():
    feed = build_feed(("051", None, [(STOP, NOW_EPOCH + 300, None)]))
    assert minutes_of(parse(feed)) == [("051", 5)]


def test_past_arrival_excluded():
    feed = build_feed(("051", 1, [(STOP, NOW_EPOCH - 120, None)]))
    assert parse(feed) == []


def test_beyond_lookahead_excluded():
    feed = build_feed(("051", 1, [(STOP, NOW_EPOCH + 120 * 60, None)]))
    assert parse(feed) == []


def test_departure_used_when_no_arrival():
    feed = build_feed(("052", 1, [(STOP, None, NOW_EPOCH + 600)]))
    assert minutes_of(parse(feed)) == [("052", 10)]


def test_sorted_ascending_across_routes():
    feed = build_feed(
        ("052", 1, [(STOP, NOW_EPOCH + 900, None)]),
        ("051", 1, [(STOP, NOW_EPOCH + 240, None)]),
        ("051", 1, [(STOP, NOW_EPOCH + 1500, None)]),
    )
    assert minutes_of(parse(feed)) == [("051", 4), ("052", 15), ("051", 25)]
