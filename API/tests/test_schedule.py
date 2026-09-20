from datetime import datetime, timedelta

import pytz

from API_Endpoints.helpers.schedule import CIRCUIT_IDS, _row_to_race, _session_dict, find_current_race


def test_session_dict_handles_nat():
    assert _session_dict("NaT") == {"date": None, "time": None}
    assert _session_dict(None) == {"date": None, "time": None}


def test_session_dict_formats_real_datetime():
    dt = datetime(2026, 5, 24, 13, 0, 0)
    assert _session_dict(dt) == {"date": "2026-05-24", "time": "13:00:00Z"}


def _make_row(**overrides):
    row = {
        "RoundNumber": 8,
        "EventName": "Monaco Grand Prix",
        "OfficialEventName": "FORMULA 1 MONACO GRAND PRIX 2026",
        "Location": "Monaco",
        "Country": "Monaco",
        "Session1": "Practice 1",
        "Session1DateUtc": "NaT",
        "Session2": "Practice 2",
        "Session2DateUtc": "NaT",
        "Session3": "Qualifying",
        "Session3DateUtc": datetime(2026, 5, 23, 13, 0, 0),
        "Session4": None,
        "Session4DateUtc": "NaT",
        "Session5": "Race",
        "Session5DateUtc": datetime(2026, 5, 24, 13, 0, 0),
    }
    row.update(overrides)
    return row


def test_row_to_race_maps_sessions_and_circuit_id():
    race = _row_to_race(_make_row())

    assert race["round"] == 8
    assert race["raceName"] == "Monaco Grand Prix"
    assert race["circuit"]["circuitId"] == "monaco"
    assert race["schedule"]["qualy"]["date"] == "2026-05-23"
    assert race["schedule"]["race"]["date"] == "2026-05-24"
    # A session type this row doesn't carry stays present-but-empty, not missing.
    assert race["schedule"]["sprintQualy"] == {"date": None, "time": None}


def test_row_to_race_unknown_circuit_id_is_none():
    row = _make_row(Location="Nowhereville", Country="Nowhere")
    race = _row_to_race(row)
    assert race["circuit"]["circuitId"] is None


def test_circuit_ids_has_both_monaco_spellings():
    # fastf1 has been observed to report both spellings for the same
    # physical circuit across different seasons - both must resolve.
    assert CIRCUIT_IDS[("Monaco", "Monaco")] == "monaco"
    assert CIRCUIT_IDS[("Monte Carlo", "Monaco")] == "monaco"


def _raw_session(dt):
    if dt is None:
        return {"date": None, "time": None}
    return {"date": dt.strftime("%Y-%m-%d"), "time": dt.strftime("%H:%M:%SZ")}


def _race_with_race_session(race_dt, round_num):
    return {"round": round_num, "raceName": f"Round {round_num}", "schedule": {"race": _raw_session(race_dt)}}


def test_find_current_race_picks_earliest_still_upcoming():
    now = datetime.now(pytz.UTC)
    past = _race_with_race_session(now - timedelta(days=10), 1)
    soon = _race_with_race_session(now + timedelta(days=3), 2)
    later = _race_with_race_session(now + timedelta(days=10), 3)

    result = find_current_race([later, past, soon], now)

    assert result["round"] == 2


def test_find_current_race_none_when_season_is_over():
    now = datetime.now(pytz.UTC)
    past = _race_with_race_session(now - timedelta(days=10), 1)

    assert find_current_race([past], now) is None


def test_find_current_race_skips_races_missing_a_race_session():
    now = datetime.now(pytz.UTC)
    broken = {"round": 1, "raceName": "No schedule", "schedule": {"race": {"date": None, "time": None}}}
    soon = _race_with_race_session(now + timedelta(days=1), 2)

    result = find_current_race([broken, soon], now)

    assert result["round"] == 2
