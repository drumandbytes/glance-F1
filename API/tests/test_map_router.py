import pandas as pd

import API_Endpoints.map.router as router_module
from API_Endpoints.map.router import historical_event_matches, normalize_name


def test_normalize_name_strips_accents_and_case():
    assert normalize_name("Montréal") == normalize_name("montreal")
    assert normalize_name(" São Paulo ") == "sao paulo"
    assert normalize_name(None) == ""


def _event(**overrides):
    event = {"Location": "Spa-Francorchamps", "Country": "Belgium", "EventName": "Belgian Grand Prix"}
    event.update(overrides)
    return event


def test_matches_on_location_and_country():
    assert historical_event_matches(_event(), "Spa-Francorchamps", "Belgium", "Something Else")


def test_matches_on_event_name_alone():
    assert historical_event_matches(_event(Location="Different", Country="Different"), None, None, "Belgian Grand Prix")


def test_no_match_when_nothing_lines_up():
    assert not historical_event_matches(_event(), "Nowhere", "Nowhere", "Not This Race")


def test_location_alone_is_not_enough_without_matching_country():
    assert not historical_event_matches(_event(), "Spa-Francorchamps", "Wrong Country", None)


def test_accent_and_case_insensitive_matching():
    assert historical_event_matches(_event(Location="Montréal"), "montreal", "Belgium", None)


def _schedule_df(rows):
    return pd.DataFrame(rows)


def test_no_schedule_match_skips_year_without_a_live_lookup(monkeypatch):
    # Real bug, caught against live data: a year with no matching event at
    # all (e.g. Shanghai during its COVID-era calendar suspension) used to
    # fall through to a fuzzy city+country guess against fastf1.get_session,
    # which was observed to silently resolve to a totally unrelated race
    # ("Mexico City Mexico" corrected to "Austrian Grand Prix") and still
    # cost a full expensive session-load attempt before being discarded.
    # Confirms it's skipped instead - no live lookup for that year at all.
    calls = []

    def fake_get_event_schedule(year):
        # 2024 (the current season) and 2023 both have no matching event -
        # walk-back now tries the current year first, so both must be
        # covered to actually exercise the skip-without-a-live-lookup path.
        if year in (2024, 2023):
            return _schedule_df([{"Location": "Unrelated", "Country": "Nowhere", "EventName": "Unrelated Grand Prix"}])
        return _schedule_df([{"Location": "Shanghai", "Country": "China", "EventName": "Chinese Grand Prix"}])

    def fake_generate_track_map_svg(**kwargs):
        calls.append(kwargs)
        return "<svg>fake</svg>"

    monkeypatch.setattr(router_module.fastf1, "get_event_schedule", fake_get_event_schedule)
    monkeypatch.setattr(router_module, "generate_track_map_svg", fake_generate_track_map_svg)

    data = {
        "race": [{
            "raceName": "Chinese Grand Prix",
            "circuit": {"city": "Shanghai", "country": "China", "circuitName": "Shanghai International Circuit"},
        }],
        "season": 2024,
    }

    svg = router_module.generate_historical_track_map(data)

    assert svg == "<svg>fake</svg>"
    # 2024 and 2023 both had no matching event and must not have triggered a
    # live lookup - exactly one call, for 2022 (the first year that actually
    # matches), not one wasted guess per skipped year.
    assert len(calls) == 1
    assert calls[0]["year"] == 2022
    assert calls[0]["race_name"] == "Chinese Grand Prix"


def test_current_season_race_already_run_needs_no_walk_back(monkeypatch):
    # Track layouts don't change year to year, but a circuit whose race
    # already happened this season has its own data sitting right there -
    # confirms the walk-back tries the current season first rather than
    # skipping straight past it into history for no reason.
    calls = []

    def fake_get_event_schedule(year):
        return _schedule_df([{"Location": "Shanghai", "Country": "China", "EventName": "Chinese Grand Prix"}])

    def fake_generate_track_map_svg(**kwargs):
        calls.append(kwargs)
        return "<svg>fake</svg>"

    monkeypatch.setattr(router_module.fastf1, "get_event_schedule", fake_get_event_schedule)
    monkeypatch.setattr(router_module, "generate_track_map_svg", fake_generate_track_map_svg)

    data = {
        "race": [{
            "raceName": "Chinese Grand Prix",
            "circuit": {"city": "Shanghai", "country": "China", "circuitName": "Shanghai International Circuit"},
        }],
        "season": 2024,
    }

    router_module.generate_historical_track_map(data)

    assert len(calls) == 1
    assert calls[0]["year"] == 2024


def test_current_season_falls_back_to_fp1_before_quali_happens(monkeypatch):
    # A brand-new circuit's debut weekend has no history to fall back to at
    # all - FP1 usually runs before qualifying, so try it too within the
    # current season rather than waiting on Q alone.
    calls = []

    def fake_get_event_schedule(year):
        return _schedule_df([{"Location": "Shanghai", "Country": "China", "EventName": "Chinese Grand Prix"}])

    def fake_generate_track_map_svg(**kwargs):
        calls.append(kwargs)
        if kwargs["session_type"] == "Q":
            raise ValueError("qualifying hasn't happened yet")
        return "<svg>fp1</svg>"

    monkeypatch.setattr(router_module.fastf1, "get_event_schedule", fake_get_event_schedule)
    monkeypatch.setattr(router_module, "generate_track_map_svg", fake_generate_track_map_svg)

    data = {
        "race": [{
            "raceName": "Chinese Grand Prix",
            "circuit": {"city": "Shanghai", "country": "China", "circuitName": "Shanghai International Circuit"},
        }],
        "season": 2024,
    }

    svg = router_module.generate_historical_track_map(data)

    assert svg == "<svg>fp1</svg>"
    assert [c["session_type"] for c in calls] == ["Q", "FP1"]
    assert all(c["year"] == 2024 for c in calls)


def test_historical_years_never_try_fp1(monkeypatch):
    calls = []

    def fake_get_event_schedule(year):
        return _schedule_df([{"Location": "Shanghai", "Country": "China", "EventName": "Chinese Grand Prix"}])

    def fake_generate_track_map_svg(**kwargs):
        calls.append(kwargs)
        if kwargs["year"] == 2024:
            raise ValueError("no data yet")
        return "<svg>historical</svg>"

    monkeypatch.setattr(router_module.fastf1, "get_event_schedule", fake_get_event_schedule)
    monkeypatch.setattr(router_module, "generate_track_map_svg", fake_generate_track_map_svg)

    data = {
        "race": [{
            "raceName": "Chinese Grand Prix",
            "circuit": {"city": "Shanghai", "country": "China", "circuitName": "Shanghai International Circuit"},
        }],
        "season": 2024,
    }

    svg = router_module.generate_historical_track_map(data)

    assert svg == "<svg>historical</svg>"
    session_types_by_year = {}
    for c in calls:
        session_types_by_year.setdefault(c["year"], []).append(c["session_type"])
    assert session_types_by_year[2024] == ["Q", "FP1"]
    assert session_types_by_year[2023] == ["Q"]
