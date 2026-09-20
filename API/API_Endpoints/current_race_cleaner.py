from fastapi import APIRouter
from fastapi_cache import FastAPICache
from datetime import datetime, timedelta
import os

from .helpers.schedule import get_season_schedule
from .helpers.time_functions import TZ, MT, UTC, convert_to_mt, get_datetime
from .helpers.global_vars import default_expire

router = APIRouter()

@router.get("/", summary="Fetch next race")
async def get_next_race():
    cache = FastAPICache.get_backend()
    cache_key = "f1:next_race"

    cached = await cache.get(cache_key)
    if cached:
        return cached

    year = datetime.now().year
    try:
        races = get_season_schedule(year)
    except Exception as e:
        return {"error": f"Exception while fetching: {e}"}

    races = sorted(races, key=lambda r: r.get("schedule", {}).get("race", {}).get("date", ""))

    # Loop through list in order until find first race with date past today.
    next_race = None
    now = datetime.now(MT)
    for race in races:
        race_date_str = race.get("schedule", {}).get("race", {}).get("date")
        race_time_str = race.get("schedule", {}).get("race", {}).get("time")
        if not race_date_str or not race_time_str:
            continue

        race_datetime_utc = datetime.strptime(f"{race_date_str}T{race_time_str}", "%Y-%m-%dT%H:%M:%SZ")
        race_datetime_utc = UTC.localize(race_datetime_utc)

        race_datetime_local = race_datetime_utc.astimezone(MT)
        if race_datetime_local >= now:
            next_race = race
            break

    if not next_race:
        return {"message": "No upcoming race found"}

    # Convert schedule times
    schedule = next_race.get("schedule", {})
    for session, val in schedule.items():
        if val["date"] and val["time"]:
            dt_mt = convert_to_mt(val["date"], val["time"])
            val["date"] = dt_mt.strftime("%Y-%m-%d")
            val["time"] = dt_mt.strftime("%-I:%M%p")
            val["datetime_rfc3339"] = dt_mt.isoformat()

    calendar_round = next_race.get("round")

    sorted_schedule = sorted(schedule.items(), key=get_datetime)

    session_name_readable = {
        "fp1": "Free Practice 1",
        "fp2": "Free Practice 2",
        "fp3": "Free Practice 3",
        "qualy": "Qualifying",
        "sprintQualy": "Sprint Qualifying",
        "sprintRace": "Sprint Race",
        "race": "Race"
    }

    next_event = None
    try:
        detail_level = os.environ.get("EVENT_DETAIL").strip()
    except Exception:
        detail_level = 'main'

    for session_name, session_data in sorted_schedule:
        event_datetime_str = session_data.get("datetime_rfc3339")
        event_date_str = session_data.get("date")
        event_time_str = session_data.get("time")
        if not event_datetime_str:
            continue

        if detail_level == "main":
            if session_name in ('fp1', 'fp2', 'fp3'):
                continue
        elif detail_level == "race":
            if session_name not in ('race', 'sprintRace'):
                continue
        elif detail_level == "detailed":
            pass
        else:
            raise ValueError("Select one of: 'main', 'race', or 'detailed'. No selection defaults to main.")

        try:
            dt = datetime.fromisoformat(event_datetime_str)
            if dt > datetime.now(MT):
                next_event = {
                    "session": session_name_readable.get(session_name, session_name.title()),
                    "date": event_date_str,
                    "time": event_time_str,
                    "datetime": event_datetime_str
                }
                break
        except Exception:
            continue

    # Cache expiry logic based on race time
    now = datetime.now(MT)

    race_session = next_race.get("schedule", {}).get("race")
    race_dt = None
    if race_session and race_session.get("datetime_rfc3339"):
        race_dt = datetime.fromisoformat(race_session["datetime_rfc3339"])

    expire = default_expire
    expiry_dt = now + timedelta(seconds=default_expire)
    if next_event and next_event.get("datetime"):
        try:
            next_event_dt = datetime.fromisoformat(next_event["datetime"])
            if next_event_dt > now:
                # Cache until next session starts
                expire = max(1, int((next_event_dt - now).total_seconds()))
                expiry_dt = next_event_dt
            else:
                expire = default_expire
                expiry_dt = now + timedelta(seconds=expire)
        except Exception:
            expire = default_expire
            expiry_dt = now + timedelta(seconds=expire)

    elif race_dt:
        if now < race_dt + timedelta(hours=1):
            # Race just ended, wait minimum of 1 hour
            expiry_dt = race_dt + timedelta(hours=1)
            expire = int((expiry_dt - now).total_seconds())
        else:
            # 1 hour after race, poll every hour
            expire = default_expire
            expiry_dt = now + timedelta(seconds=expire)
    else:
        expire = default_expire
        expiry_dt = now + timedelta(seconds=expire)

    # Output data
    response_data = {
        "season": year,
        "round": calendar_round,
        "timezone": TZ,
        "next_event": next_event,
        "cache_expires": expiry_dt.isoformat(),
        "race": [next_race]
    }

    await cache.set(cache_key, response_data, expire=expire)
    return response_data
