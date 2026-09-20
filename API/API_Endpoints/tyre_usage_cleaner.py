"""Tyre compound usage per session for the current race weekend - what each
driver actually ran in FP1/FP2/FP3/Q/Race (or the sprint-weekend
equivalents), sourced from fastf1 lap data.

Deliberately usage-only. FIA's per-driver tyre SELECTION (how many sets of
each compound a driver chose within their fixed weekend budget) isn't
available from fastf1, Ergast, or OpenF1 as structured data - and a
hardcoded default-split baseline (the common "8 soft / 3 medium / 2 hard"
assumption) would silently be wrong for any driver who picked a different
mix, on top of the sprint-weekend quota itself changing between seasons.
This reports only what's independently verifiable from timing data: what
was actually run, when - no assumptions about what's left.
"""
from datetime import datetime

import fastf1
from fastapi import APIRouter
from fastapi_cache import FastAPICache
from starlette.concurrency import run_in_threadpool

from .helpers.global_vars import default_expire
from .helpers.schedule import find_current_race, get_season_schedule, parse_session_datetime
from .helpers.time_functions import MT

router = APIRouter()

# Our schedule keys, in on-track order, mapped to the identifiers
# fastf1.get_session() expects. A normal weekend only ever populates a
# subset of these (sprintQualy/sprintRace stay empty outside sprint
# weekends) - schedule.py's _row_to_race already leaves absent ones as
# {"date": None, "time": None}, which _session_has_happened treats as "no".
_SESSION_KEY_TO_FASTF1_TYPE = {
    "fp1": "FP1",
    "fp2": "FP2",
    "fp3": "FP3",
    "sprintQualy": "SQ",
    "sprintRace": "S",
    "qualy": "Q",
    "race": "R",
}


def _session_has_happened(schedule: dict, session_key: str, now) -> bool:
    dt = parse_session_datetime(schedule.get(session_key, {}))
    return dt is not None and dt <= now


def _stints_for_session(round_number: int, year: int, fastf1_type: str) -> list[dict]:
    # Round number, not a race-name/city+country guess - we already have a
    # validated identifier from our own schedule data, no fuzzy matching
    # needed (unlike the old track-map generation this app used to do).
    session = fastf1.get_session(year, round_number, fastf1_type)
    session.load(laps=True, telemetry=False, weather=False, messages=False)

    if session.laps is None or session.laps.empty:
        return []

    # session.laps carries several dozen columns (sector times, speed traps,
    # track status, ...) - select the 3 actually used immediately, rather
    # than keep the full frame (measured ~160MB peak RSS for one session's
    # worth) alive for the rest of this function. Driver/Compound are both
    # low-cardinality (~24 drivers, ~7 compounds) - categorical dtype instead
    # of the default generic object dtype shrinks this further.
    laps = session.laps.loc[:, ["Driver", "Stint", "Compound"]].astype({
        "Driver": "category",
        "Compound": "category",
    })

    stints = (
        laps.groupby(["Driver", "Stint"], observed=True)["Compound"]
        .agg(["first", "count"])
        .reset_index()
        .sort_values(["Driver", "Stint"])
    )

    by_driver: dict[str, list[dict]] = {}
    for _, row in stints.iterrows():
        by_driver.setdefault(str(row["Driver"]), []).append({
            "compound": str(row["first"]),
            "laps": int(row["count"]),
        })

    return [{"driver": driver, "stints": stint_list} for driver, stint_list in by_driver.items()]


def _tyre_usage_for_weekend(race: dict) -> dict:
    schedule = race.get("schedule", {})
    year = int(race.get("season") or datetime.now().year)
    round_number = race["round"]
    now = datetime.now(MT)

    sessions = {}
    for session_key, fastf1_type in _SESSION_KEY_TO_FASTF1_TYPE.items():
        if not _session_has_happened(schedule, session_key, now):
            sessions[session_key] = None
            continue
        try:
            sessions[session_key] = _stints_for_session(round_number, year, fastf1_type)
        except Exception:
            # Scheduled time passed but no data yet (just-finished session,
            # red flag, cancelled) - leave it absent rather than fail the
            # whole weekend's response over one session.
            sessions[session_key] = None

    return {
        "season": year,
        "round": round_number,
        "raceName": race.get("raceName"),
        "sessions": sessions,
    }


@router.get("/", summary="Fetch tyre usage for the current race weekend")
async def get_tyre_usage():
    cache = FastAPICache.get_backend()
    cache_key = "f1:tyre_usage"

    cached = await cache.get(cache_key)
    if cached:
        return cached

    year = datetime.now().year
    try:
        races = get_season_schedule(year)
    except Exception as e:
        return {"error": f"Exception while fetching: {e}"}

    race = find_current_race(races, datetime.now(MT))
    if not race:
        return {"message": "No current race weekend found"}
    race = dict(race, season=year)

    response_data = await run_in_threadpool(_tyre_usage_for_weekend, race)

    await cache.set(cache_key, response_data, expire=default_expire)
    return response_data
