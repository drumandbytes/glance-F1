from datetime import datetime, timedelta

import pytest
import pytz
from freezegun import freeze_time

import API_Endpoints.current_race_cleaner as crc

_EMPTY = {"date": None, "time": None}


def _raw_session(dt):
    if dt is None:
        return dict(_EMPTY)
    return {"date": dt.strftime("%Y-%m-%d"), "time": dt.strftime("%H:%M:%SZ")}


def _race(race_dt=None, qualy_dt=None, fp1_dt=None, fp2_dt=None, fp3_dt=None,
          sprint_dt=None, sprint_qualy_dt=None, event_name="Test Grand Prix", round_num=1):
    return {
        "round": round_num,
        "raceName": event_name,
        "url": None,
        "schedule": {
            "fp1": _raw_session(fp1_dt),
            "fp2": _raw_session(fp2_dt),
            "fp3": _raw_session(fp3_dt),
            "qualy": _raw_session(qualy_dt),
            "sprintQualy": _raw_session(sprint_qualy_dt),
            "sprintRace": _raw_session(sprint_dt),
            "race": _raw_session(race_dt),
        },
        "circuit": {
            "circuitId": "test",
            "circuitName": "Test Circuit",
            "url": None,
            "country": "Testland",
            "city": "Testville",
        },
    }


async def test_next_event_skips_practice_sessions_in_main_detail(monkeypatch):
    # EVENT_DETAIL defaults to "main" (conftest.py)
    now = datetime.now(pytz.UTC)
    race = _race(race_dt=now + timedelta(days=2), qualy_dt=now + timedelta(days=1),
                 fp1_dt=now + timedelta(hours=1))
    monkeypatch.setattr(crc, "get_season_schedule", lambda year: [race])

    result = await crc.get_next_race()

    assert result["next_event"]["session"] == "Qualifying"


async def test_race_detail_level_only_considers_race_sessions(monkeypatch):
    monkeypatch.setenv("EVENT_DETAIL", "race")
    now = datetime.now(pytz.UTC)
    race = _race(race_dt=now + timedelta(days=2), qualy_dt=now + timedelta(days=1))
    monkeypatch.setattr(crc, "get_season_schedule", lambda year: [race])

    result = await crc.get_next_race()

    assert result["next_event"]["session"] == "Race"


async def test_detailed_level_picks_earliest_session(monkeypatch):
    monkeypatch.setenv("EVENT_DETAIL", "detailed")
    now = datetime.now(pytz.UTC)
    race = _race(race_dt=now + timedelta(days=2), fp1_dt=now + timedelta(hours=1))
    monkeypatch.setattr(crc, "get_season_schedule", lambda year: [race])

    result = await crc.get_next_race()

    assert result["next_event"]["session"] == "Free Practice 1"


async def test_invalid_detail_level_raises(monkeypatch):
    monkeypatch.setenv("EVENT_DETAIL", "bogus")
    now = datetime.now(pytz.UTC)
    race = _race(race_dt=now + timedelta(days=1), fp1_dt=now + timedelta(hours=1))
    monkeypatch.setattr(crc, "get_season_schedule", lambda year: [race])

    with pytest.raises(ValueError):
        await crc.get_next_race()


async def test_no_upcoming_race_returns_message(monkeypatch):
    now = datetime.now(pytz.UTC)
    past_race = _race(race_dt=now - timedelta(days=10))
    monkeypatch.setattr(crc, "get_season_schedule", lambda year: [past_race])

    result = await crc.get_next_race()

    assert result == {"message": "No upcoming race found"}


async def test_cache_expires_at_next_event(monkeypatch):
    now = datetime.now(pytz.UTC)
    qualy_dt = now + timedelta(hours=5)
    race = _race(race_dt=now + timedelta(days=1), qualy_dt=qualy_dt)
    monkeypatch.setattr(crc, "get_season_schedule", lambda year: [race])

    result = await crc.get_next_race()

    expiry = datetime.fromisoformat(result["cache_expires"])
    assert abs((expiry - qualy_dt).total_seconds()) < 5


async def test_post_race_branch_when_next_event_resolves_to_none(monkeypatch):
    # A deliberately narrow boundary: the outer "is this race still upcoming"
    # check uses >=, the per-session "is this session still upcoming" check
    # uses > - freezing time lets the race session land exactly on `now`,
    # which passes the first check but not the second, so every session
    # (including "race" itself) is judged already-passed and next_event
    # resolves to None even though a next_race was found.
    frozen = datetime(2026, 5, 24, 13, 0, 0, tzinfo=pytz.UTC)

    with freeze_time(frozen):
        race = _race(race_dt=frozen, qualy_dt=frozen - timedelta(hours=2))
        monkeypatch.setattr(crc, "get_season_schedule", lambda year: [race])

        result = await crc.get_next_race()

        assert result["next_event"] is None
        expiry = datetime.fromisoformat(result["cache_expires"])
        assert abs((expiry - (frozen + timedelta(hours=1))).total_seconds()) < 1
