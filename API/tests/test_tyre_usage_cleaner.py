from datetime import datetime, timedelta

import pandas as pd
import pytz

import API_Endpoints.tyre_usage_cleaner as tyre_usage
from API_Endpoints.tyre_usage_cleaner import _session_has_happened, _stints_for_session, _tyre_usage_for_weekend


def _raw_session(dt):
    if dt is None:
        return {"date": None, "time": None}
    return {"date": dt.strftime("%Y-%m-%d"), "time": dt.strftime("%H:%M:%SZ")}


def test_session_has_happened_true_for_past():
    now = datetime.now(pytz.UTC)
    schedule = {"fp1": _raw_session(now - timedelta(hours=1))}
    assert _session_has_happened(schedule, "fp1", now)


def test_session_has_happened_false_for_future():
    now = datetime.now(pytz.UTC)
    schedule = {"fp1": _raw_session(now + timedelta(hours=1))}
    assert not _session_has_happened(schedule, "fp1", now)


def test_session_has_happened_false_when_missing():
    now = datetime.now(pytz.UTC)
    assert not _session_has_happened({}, "sprintQualy", now)


class _FakeSession:
    def __init__(self, laps):
        self.laps = laps
        self.loaded_with = None

    def load(self, **kwargs):
        self.loaded_with = kwargs


def test_stints_for_session_groups_by_driver_and_stint(monkeypatch):
    laps = pd.DataFrame([
        {"Driver": "VER", "Stint": 1.0, "Compound": "MEDIUM"},
        {"Driver": "VER", "Stint": 1.0, "Compound": "MEDIUM"},
        {"Driver": "VER", "Stint": 2.0, "Compound": "SOFT"},
        {"Driver": "HAM", "Stint": 1.0, "Compound": "HARD"},
    ])
    fake_session = _FakeSession(laps)

    def fake_get_session(year, round_number, fastf1_type):
        assert (year, round_number, fastf1_type) == (2026, 15, "FP1")
        return fake_session

    monkeypatch.setattr(tyre_usage.fastf1, "get_session", fake_get_session)

    result = _stints_for_session(15, 2026, "FP1")

    # No telemetry/weather/messages - this is meant to stay light.
    assert fake_session.loaded_with == {"laps": True, "telemetry": False, "weather": False, "messages": False}

    by_driver = {d["driver"]: d["stints"] for d in result}
    assert by_driver["VER"] == [{"compound": "MEDIUM", "laps": 2}, {"compound": "SOFT", "laps": 1}]
    assert by_driver["HAM"] == [{"compound": "HARD", "laps": 1}]


def test_stints_for_session_empty_laps_returns_empty_list(monkeypatch):
    fake_session = _FakeSession(pd.DataFrame(columns=["Driver", "Stint", "Compound"]))
    monkeypatch.setattr(tyre_usage.fastf1, "get_session", lambda *a: fake_session)

    assert _stints_for_session(15, 2026, "FP1") == []


def test_tyre_usage_for_weekend_skips_future_and_tolerates_a_failed_session(monkeypatch):
    now = datetime.now(pytz.UTC)
    race = {
        "round": 15,
        "raceName": "Azerbaijan Grand Prix",
        "season": 2026,
        "schedule": {
            "fp1": _raw_session(now - timedelta(days=1)),   # past - succeeds
            "fp2": _raw_session(now - timedelta(hours=2)),  # past - fails to load
            "fp3": _raw_session(now + timedelta(hours=1)),  # future - skipped
            "sprintQualy": {"date": None, "time": None},
            "sprintRace": {"date": None, "time": None},
            "qualy": _raw_session(now + timedelta(hours=2)),
            "race": _raw_session(now + timedelta(days=1)),
        },
    }

    def fake_stints(round_number, year, fastf1_type):
        if fastf1_type == "FP1":
            return [{"driver": "VER", "stints": [{"compound": "MEDIUM", "laps": 10}]}]
        raise RuntimeError("no data yet")

    monkeypatch.setattr(tyre_usage, "_stints_for_session", fake_stints)

    result = _tyre_usage_for_weekend(race)

    assert result["season"] == 2026
    assert result["round"] == 15
    assert result["raceName"] == "Azerbaijan Grand Prix"
    assert result["sessions"]["fp1"] == [{"driver": "VER", "stints": [{"compound": "MEDIUM", "laps": 10}]}]
    assert result["sessions"]["fp2"] is None  # scheduled time passed, but the fetch itself failed
    assert result["sessions"]["fp3"] is None  # hasn't happened yet
    assert result["sessions"]["sprintQualy"] is None  # not a sprint weekend
    assert result["sessions"]["qualy"] is None
    assert result["sessions"]["race"] is None


async def test_get_tyre_usage_dispatches_schedule_and_usage_to_threadpool(monkeypatch):
    now = datetime.now(pytz.UTC)
    race = {
        "round": 15,
        "raceName": "Test Grand Prix",
        "schedule": {"race": _raw_session(now + timedelta(days=1))},
    }
    response = {"season": now.year, "round": 15, "raceName": "Test Grand Prix", "sessions": {}}
    calls = []

    def fake_schedule(year):
        return [race]

    def fake_usage(selected_race):
        assert selected_race == dict(race, season=now.year)
        return response

    async def fake_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(tyre_usage, "get_season_schedule", fake_schedule)
    monkeypatch.setattr(tyre_usage, "_tyre_usage_for_weekend", fake_usage)
    monkeypatch.setattr(tyre_usage, "run_in_threadpool", fake_threadpool)

    result = await tyre_usage.get_tyre_usage()

    assert calls == [
        (fake_schedule, (now.year,), {}),
        (fake_usage, (dict(race, season=now.year),), {}),
    ]
    assert result == response


async def test_get_tyre_usage_returns_message_when_no_current_race(monkeypatch):
    monkeypatch.setattr(tyre_usage, "get_season_schedule", lambda year: [])

    result = await tyre_usage.get_tyre_usage()

    assert result == {"message": "No current race weekend found"}


async def test_get_tyre_usage_returns_cached_response(monkeypatch):
    cache = tyre_usage.FastAPICache.get_backend()
    await cache.set("f1:tyre_usage", {"cached": True}, expire=60)

    def boom(*a, **kw):
        raise AssertionError("should not fetch the schedule when cache hits")

    monkeypatch.setattr(tyre_usage, "get_season_schedule", boom)

    result = await tyre_usage.get_tyre_usage()

    assert result == {"cached": True}
