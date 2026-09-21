from fastapi import APIRouter
from fastapi_cache import FastAPICache
from datetime import datetime

from fastf1.ergast import Ergast
from starlette.concurrency import run_in_threadpool

from .helpers.functions import country_to_code, format_team_name
from .helpers.global_vars import nationality_map
from .helpers.time_functions import MT

router = APIRouter()

@router.get("/", summary="Fetch current drivers championship")
async def get_drivers_championship():
    cache = FastAPICache.get_backend()
    cache_key = "drivers_championship"

    cached = await cache.get(cache_key)
    if cached:
        return cached

    season = datetime.now(MT).year
    ergast = Ergast()
    standings = await run_in_threadpool(ergast.get_driver_standings, season=season)
    standing_data = standings.content[0]

    results = []
    for _, row in standing_data.iterrows():
        if row["driverNationality"] in nationality_map:
            row["driverNationality"] = nationality_map[row["driverNationality"]]
        else:
            row["driverNationality"] = ""

        results.append({
            "surname": row["familyName"],
            "position": row["position"],
            "points": row["points"],
            "teamId": format_team_name(row["constructorNames"][0]),
            "country": row["driverNationality"],
            "flag": country_to_code(row["driverNationality"])
        })


    response_data = {
        "season": season, 
        "drivers": results}

    await cache.set(cache_key, response_data, expire=600)
    return response_data