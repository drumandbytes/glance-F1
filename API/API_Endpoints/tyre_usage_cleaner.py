from datetime import datetime

from .helpers.global_vars import default_expire
from .helpers.schedule import get_season_schedule, find_current_race, parse_session_datetime
from .helpers.time_functions import MT
from .cache import cache_manager

async def get_tyre_usage(request):
    cache_key = "f1:tyre_usage"

    cached = await cache_manager.get(cache_key)
    if cached:
        return cached

    year = datetime.now().year
    try:
        races = await get_season_schedule(year)
    except Exception as e:
        return {"error": f"Exception while fetching: {e}"}

    race = find_current_race(races, datetime.now(MT))
    if not race:
        return {"message": "No current race weekend found"}

    round_number = race.get("round")

    response_data = {
        "season": year,
        "round": round_number,
        "raceName": race.get("raceName"),
        "sessions": {},
    }

    await cache_manager.set(cache_key, response_data, expire=default_expire)
    return response_data
