from datetime import datetime

from .data_sources import fetch_constructor_standings
from .helpers.functions import country_to_code
from .helpers.global_vars import nationality_map
from .helpers.time_functions import MT
from .cache import cache_manager

async def get_constructors_championship(request):
    cache_key = "constructors_championship"
    cached = await cache_manager.get(cache_key)
    if cached:
        return cached

    try:
        season = datetime.now(MT).year
        standing_data = await fetch_constructor_standings(season)
        
        results = []
        for standing in standing_data.get("ConstructorStandings", []):
            constructor = standing.get("Constructor", {})
            nationality = constructor.get("nationality", "")
            
            if nationality in nationality_map:
                nationality = nationality_map[nationality]
            
            results.append({
                "team": constructor.get("name", ""),
                "position": int(standing.get("position", 0)),
                "points": int(standing.get("points", 0)),
                "wins": int(standing.get("wins", 0)),
                "country": nationality,
                "flag": country_to_code(nationality),
                "wiki": constructor.get("url", "")
            })

        response_data = {
            "season": season,
            "constructors": results
        }

        await cache_manager.set(cache_key, response_data, expire=600)
        return response_data
    
    except Exception as e:
        return {"error": str(e)}