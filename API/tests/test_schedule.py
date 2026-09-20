from datetime import datetime

from API_Endpoints.helpers.schedule import CIRCUIT_IDS, _row_to_race, _session_dict


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
