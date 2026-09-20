from fastapi import APIRouter
from fastapi_cache import FastAPICache
from datetime import datetime, timedelta
import pandas as pd

from fastf1.ergast import Ergast

from .helpers.functions import country_to_code
from .helpers.global_vars import nationality_map
from .helpers.time_functions import MT

router = APIRouter()


def format_time(total_race_time, is_winner: bool):
    if pd.isna(total_race_time):
        return None
    total_seconds = total_race_time.total_seconds()
    if not is_winner:
        return f"+{total_seconds:.3f}"
    h, rem = divmod(int(total_seconds), 3600)
    m, s = divmod(rem, 60)
    ms = int(round((total_seconds - int(total_seconds)) * 1000))
    return f"{h}:{m:02d}:{s:02d}.{ms:03d}" if h else f"{m}:{s:02d}.{ms:03d}"


@router.get("/", summary="Fetch last race results")
async def get_last_race():
    cache = FastAPICache.get_backend()
    cache_key = "f1:last_race"

    cached = await cache.get(cache_key)
    if cached:
        return cached

    ergast = Ergast()
    try:
        res = ergast.get_race_results(season="current", round="last")
        race_info = res.description.iloc[0]
        driver_results = res.content[0]
    except Exception as e:
        return {"error": f"Exception while fetching: {e}"}

    results = []
    for _, row in driver_results.iterrows():
        nationality = row.get("driverNationality", "")
        if nationality in nationality_map:
            nationality = nationality_map[nationality]

        # positionText is non-numeric ("R" retired, "D" disqualified, etc.)
        # for anyone not classified with a normal finish - a numeric
        # positionText still applies to a car that finished a lap down, so
        # this isn't the same check as "did they finish on the lead lap".
        is_dnf = not str(row.get("positionText")).isdigit()
        surname = row.get("familyName")
        if surname == "Kimi Antonelli":
            surname = "Antonelli"

        if is_dnf:
            laps = row.get("laps")
            time_str = f"DNF ({int(laps)})" if pd.notna(laps) else "DNF"
        else:
            time_str = format_time(row.get("totalRaceTime"), row.get("position") == 1)

        results.append({
            "position": row.get("position"),
            "surname": surname,
            "flag": country_to_code(nationality),
            "teamId": row.get("constructorId"),
            "time": time_str,
            "dnf_laps": int(row["laps"]) if is_dnf and pd.notna(row.get("laps")) else None,
        })

    expire = 86400
    expiry_dt = datetime.now(MT) + timedelta(days=1)

    response_data = {
        "season": int(race_info["season"]),
        "round": int(race_info["round"]),
        "raceName": race_info["raceName"],
        "date": race_info["raceDate"].strftime("%Y-%m-%d") if pd.notna(race_info["raceDate"]) else None,
        "cache_expires": expiry_dt.isoformat(),
        "results": results,
    }

    await cache.set(cache_key, response_data, expire=expire)
    return response_data
