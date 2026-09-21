from datetime import timedelta

import pandas as pd
import pytest

import API_Endpoints.constructors_cleaner as constructors
import API_Endpoints.drivers_cleaner as drivers
import API_Endpoints.last_race_cleaner as last_race


@pytest.mark.parametrize(
    ("module", "endpoint", "cache_key"),
    [
        (constructors, constructors.get_constructors_championship, "constructors_championship"),
        (drivers, drivers.get_drivers_championship, "drivers_championship"),
    ],
)
async def test_standings_cache_hit_bypasses_ergast(monkeypatch, module, endpoint, cache_key):
    cached = {"cached": True}
    await module.FastAPICache.get_backend().set(cache_key, cached, expire=60)

    def boom():
        raise AssertionError("Ergast should not be created on a cache hit")

    monkeypatch.setattr(module, "Ergast", boom)

    assert await endpoint() == cached


async def test_constructors_ergast_call_uses_threadpool_and_preserves_output(monkeypatch):
    frame = pd.DataFrame([{
        "constructorNationality": "British",
        "constructorName": "McLaren",
        "position": 1,
        "points": 100,
        "wins": 3,
        "constructorUrl": "https://example.com/mclaren",
    }])

    class FakeErgast:
        def get_constructor_standings(self, season):
            return type("Response", (), {"content": [frame]})()

    calls = []

    async def fake_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    ergast = FakeErgast()
    monkeypatch.setattr(constructors, "Ergast", lambda: ergast)
    monkeypatch.setattr(constructors, "run_in_threadpool", fake_threadpool)

    result = await constructors.get_constructors_championship()

    assert calls == [(ergast.get_constructor_standings, (), {"season": result["season"]})]
    assert result == {
        "season": result["season"],
        "constructors": [{
            "team": "McLaren",
            "position": 1,
            "points": 100,
            "wins": 3,
            "country": "Great Britain",
            "flag": "gb",
            "wiki": "https://example.com/mclaren",
        }],
    }


async def test_last_race_ergast_call_uses_threadpool(monkeypatch):
    race_info = pd.DataFrame([{
        "season": 2026,
        "round": 1,
        "raceName": "Test Grand Prix",
        "raceDate": pd.Timestamp("2026-03-01"),
    }])
    results = pd.DataFrame([{
        "driverNationality": "Dutch",
        "positionText": "1",
        "familyName": "Verstappen",
        "position": 1,
        "totalRaceTime": timedelta(minutes=90),
        "constructorId": "red_bull",
        "laps": 57,
    }])

    class FakeErgast:
        def get_race_results(self, season, round):
            return type("Response", (), {"description": race_info, "content": [results]})()

    calls = []

    async def fake_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    ergast = FakeErgast()
    monkeypatch.setattr(last_race, "Ergast", lambda: ergast)
    monkeypatch.setattr(last_race, "run_in_threadpool", fake_threadpool)

    result = await last_race.get_last_race()

    assert calls == [(ergast.get_race_results, (), {"season": "current", "round": "last"})]
    assert result["raceName"] == "Test Grand Prix"
    assert result["results"][0]["surname"] == "Verstappen"


async def test_drivers_ergast_call_uses_threadpool_and_preserves_output(monkeypatch):
    frame = pd.DataFrame([{
        "driverNationality": "Dutch",
        "familyName": "Verstappen",
        "position": 1,
        "points": 100,
        "constructorNames": ["red_bull"],
    }])

    class FakeErgast:
        def get_driver_standings(self, season):
            return type("Response", (), {"content": [frame]})()

    calls = []

    async def fake_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    ergast = FakeErgast()
    monkeypatch.setattr(drivers, "Ergast", lambda: ergast)
    monkeypatch.setattr(drivers, "run_in_threadpool", fake_threadpool)

    result = await drivers.get_drivers_championship()

    assert calls == [(ergast.get_driver_standings, (), {"season": result["season"]})]
    assert result == {
        "season": result["season"],
        "drivers": [{
            "surname": "Verstappen",
            "position": 1,
            "points": 100,
            "teamId": "Red Bull",
            "country": "Netherlands",
            "flag": "nl",
        }],
    }
