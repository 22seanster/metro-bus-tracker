import asyncio

import pytest

from app.providers.base import Provider


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, results, clock, interval=10):
        super().__init__(interval=interval, stale_factor=3, clock=clock)
        self._results = iter(results)

    async def fetch(self):
        r = next(self._results)
        if isinstance(r, Exception):
            raise r
        return r


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


async def test_successful_fetch_updates_snapshot():
    clock = FakeClock()
    p = FakeProvider(["hello"], clock)
    await p.refresh_once()
    assert p.snapshot() == "hello"
    assert p.fetched_at == 1000.0
    assert p.last_error is None
    assert not p.is_stale()


async def test_error_keeps_last_data_and_records_error():
    clock = FakeClock()
    p = FakeProvider(["hello", RuntimeError("boom")], clock)
    await p.refresh_once()
    clock.t += 5
    await p.refresh_once()
    assert p.snapshot() == "hello"  # stale data kept
    assert "boom" in p.last_error
    assert p.error_count == 1


async def test_staleness_after_factor_times_interval():
    clock = FakeClock()
    p = FakeProvider(["hello"], clock, interval=10)
    await p.refresh_once()
    clock.t += 29  # < 3 * 10
    assert not p.is_stale()
    clock.t += 2  # 31 > 30
    assert p.is_stale()


async def test_no_data_yet_is_stale_with_none_snapshot():
    p = FakeProvider([], FakeClock())
    assert p.snapshot() is None
    assert p.is_stale()


async def test_backoff_grows_and_resets():
    clock = FakeClock()
    p = FakeProvider([RuntimeError("a"), RuntimeError("b"), "ok"], clock, interval=100)
    await p.refresh_once()
    assert p.next_delay() == 10  # 5 * 2**1
    await p.refresh_once()
    assert p.next_delay() == 20  # 5 * 2**2
    await p.refresh_once()
    assert p.next_delay() == 100  # success -> normal interval
    assert p.error_count == 0


async def test_status_dict_shape():
    clock = FakeClock()
    p = FakeProvider(["hello"], clock)
    await p.refresh_once()
    clock.t += 4
    s = p.status()
    assert s["age_seconds"] == 4
    assert s["stale"] is False
    assert s["error"] is None
    assert s["mock"] is False
