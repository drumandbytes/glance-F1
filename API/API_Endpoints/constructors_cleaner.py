from fastapi import APIRouter
from fastapi_cache import FastAPICache
from datetime import datetime

from fastf1.ergast import Ergast
from starlette.concurrency import run_in_threadpool

from .helpers.functions import country_to_code
from .helpers.global_vars import nationality_map
from .helpers.time_functions import MT

router = APIRouter()

@router.get("/", summary="Fetch current constructors championship")
async def get_constructors_championship():
    cache = FastAPICache.get_backend()
    cache_key = "constructors_championship"

    cached = await cache.get(cache_key)
    if cached:
        return cached

    season = datetime.now(MT).year
    ergast = Ergast()
    standings = await run_in_threadpool(ergast.get_constructor_standings, season=season)
    standing_data = standings.content[0]

    results = []
    for _, row in standing_data.iterrows():
        if row["constructorNationality"] in nationality_map:
            row["constructorNationality"] = nationality_map[row["constructorNationality"]]
        else:
            row["constructorNationality"] = ""

        results.append({
            "team": row["constructorName"],
            "position": row["position"],
            "points": row["points"],
            "wins": row["wins"],
            "country": row["constructorNationality"],
            "flag": country_to_code(row["constructorNationality"]),
            "wiki": row["constructorUrl"]
        })


    response_data = {
        "season": season, 
        "constructors": results}

    await cache.set(cache_key, response_data, expire=600)
    return response_data