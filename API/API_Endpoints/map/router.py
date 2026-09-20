from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool
import fastf1
from fastf1.exceptions import RateLimitExceededError
import httpx
from datetime import datetime
import os
import hashlib
import json
from fastapi_cache import FastAPICache

from .map_generator import generate_track_map_svg, remove_accents
from ..helpers.global_vars import NEXT_RACE_API_URL, default_expire

router = APIRouter()

# Pre-rendered by scripts/generate_track_maps.py, one file per current-season
# circuitId - see .github/workflows/regenerate-track-maps.yml (runs monthly,
# PRs whatever changed). Track layouts change rarely (once every few years,
# always between seasons), so this is the fast path for every normal request;
# live generation below only ever runs for a circuit that script hasn't
# covered yet (freshly added to the calendar since its last run).
STATIC_MAP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "track_maps")

def make_signature(data):
    return hashlib.md5(json.dumps(data, 
        sort_keys=True).encode()).hexdigest()

def generate_historical_track_map(data):
    race = data.get("race", [{}])[0]
    circuit = race.get("circuit") or {}
    country = circuit.get("country")
    city = circuit.get("city")
    track = circuit.get("circuitName")
    race_name = race.get("raceName")
    current_year = int(data.get("season", datetime.now().year))

    errors = []
    # Track layouts are static, so any year with recorded telemetry for this
    # circuit produces an identical map - the walk-back isn't about
    # freshness, it's the only way to get *any* data for a circuit whose
    # race this season hasn't happened yet. But for one that already has
    # (most of the calendar, most of the time this runs), this season's own
    # data is sitting right there - try it first instead of walking straight
    # past it into older, spottier seasons for no reason.
    for year in range(current_year, 2017, -1):
        attempts = []

        try:
            schedule = fastf1.get_event_schedule(year)
            matching_events = [
                event for _, event in schedule.iterrows()
                if historical_event_matches(event, city, country, race_name)
            ]
        except RateLimitExceededError:
            # A hard rate limit, not "this year doesn't match" - every
            # remaining attempt in this walk-back loop would fail the exact
            # same way, so retrying them is pure wasted requests against an
            # already-exceeded limit. Let it propagate instead of consuming
            # it into `errors` and trying the next year anyway.
            raise
        except Exception as e:
            errors.append(f"{year} schedule: {type(e).__name__}: {e}")
            matching_events = []

        # For the current season only, qualifying may not have happened yet
        # (a brand-new circuit's debut weekend, most notably - there's no
        # historical year to fall back to at all until *some* session has
        # run there). FP1 usually runs first, so try it too, after Q - past
        # seasons always have qualifying data already, so there's nothing to
        # fall back for.
        session_types = ["Q", "FP1"] if year == current_year else ["Q"]
        for event in matching_events:
            for session_type in session_types:
                attempts.append({
                    "year": year,
                    "race_name": event.get("EventName"),
                    "track": track,
                    "session_type": session_type,
                })

        if not attempts:
            # No event in this year's own schedule matched by location or
            # name - fastf1.get_session() only takes a fuzzy free-text query,
            # and guessing one from city+country alone has been observed to
            # silently resolve to a WRONG, unrelated race (e.g. "Mexico City
            # Mexico" corrected to "Austrian Grand Prix") for a year that
            # simply never had this circuit on the calendar (a
            # COVID-suspended season, for one real example - every walked-
            # back year is checked against that year's *own* schedule, so
            # this isn't rare). That guess used to cost a full, expensive
            # session-load attempt - each one loads laps and full-grid
            # telemetry for the whole field - before this function's own
            # match-validation caught the mismatch and discarded it, which
            # is what actually exhausts the 500-calls/hour budget after only
            # a handful of circuits. Skip the year instead.
            errors.append(f"{year}: no matching event in this year's schedule")
            continue

        for kwargs in attempts:
            try:
                return generate_track_map_svg(**kwargs)
            except RateLimitExceededError:
                raise
            except Exception as e:
                errors.append(f"{year}: {type(e).__name__}: {e}")

    raise ValueError("Could not fetch a historical track map. " + " | ".join(errors[-6:]))

def normalize_name(value):
    return remove_accents(str(value or "")).casefold().strip()

def historical_event_matches(event, city, country, race_name):
    location_matches = city and normalize_name(event.get("Location")) == normalize_name(city)
    country_matches = country and normalize_name(event.get("Country")) == normalize_name(country)
    event_name_matches = (
        race_name
        and normalize_name(event.get("EventName")) == normalize_name(race_name)
    )

    return (location_matches and country_matches) or event_name_matches

@router.get("/", summary="Fetch next track map")
async def get_dynamic_track_map():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(NEXT_RACE_API_URL)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return PlainTextResponse(f"Failed to fetch race info: {str(e)}", status_code=502)

    race = data.get("race", [{}])[0]
    circuit_id = (race.get("circuit") or {}).get("circuitId")

    if circuit_id:
        static_path = os.path.join(STATIC_MAP_DIR, f"{circuit_id}.svg")
        if os.path.isfile(static_path):
            with open(static_path) as f:
                return Response(content=f.read(), media_type="image/svg+xml")

    # Fallback: circuit not yet pre-rendered (e.g. added to the calendar
    # since the generator script's last monthly run). Cached per-circuit so
    # repeated dashboard refreshes before the next scheduled run don't each
    # re-trigger a fresh 30-90s fastf1 load.
    cache = FastAPICache.get_backend()
    cache_key = f"track_map_svg:{circuit_id or make_signature(race)}"
    cached = await cache.get(cache_key)
    if cached:
        return Response(content=cached, media_type="image/svg+xml")

    race_dt_str = race.get("schedule", {}).get("race", {}).get("datetime_rfc3339")
    if not race_dt_str:
        return PlainTextResponse("Missing race datetime", status_code=500)

    try:
        # generate_historical_track_map does a synchronous fastf1
        # session.load() that can block for 30-90s on a cold cache - run it
        # off the event loop so a single worker can still serve every other
        # (cheap, cached) endpoint while this is in flight, instead of
        # needing a second whole worker process just to survive this one
        # call.
        svg_content = await run_in_threadpool(generate_historical_track_map, data)
    except Exception as e:
        return PlainTextResponse(str(e), status_code=500)

    await cache.set(cache_key, svg_content, expire=default_expire)
    return Response(content=svg_content, media_type="image/svg+xml")
