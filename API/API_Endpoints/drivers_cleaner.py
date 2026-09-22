from datetime import datetime
from starlette.responses import JSONResponse

from .data_sources import fetch_driver_standings
from .helpers.functions import country_to_code, format_team_name
from .helpers.global_vars import nationality_map
from .helpers.time_functions import MT
from .cache import cache_manager

async def get_drivers_championship(request):
    cache_key = "drivers_championship"
    cached = await cache_manager.get(cache_key)
    if cached:
        return JSONResponse(cached)

    try:
        season = datetime.now(MT).year
        standing_data = await fetch_driver_standings(season)
        
        results = []
        for standing in standing_data.get("DriverStandings", []):
            driver = standing.get("Driver", {})
            constructor = standing.get("Constructors", [{}])[0]
            nationality = driver.get("nationality", "")
            
            if nationality in nationality_map:
                nationality = nationality_map[nationality]
            
            results.append({
                "surname": driver.get("familyName", ""),
                "position": int(standing.get("position", 0)),
                "points": int(standing.get("points", 0)),
                "teamId": format_team_name(constructor.get("constructorId", "")),
                "country": nationality,
                "flag": country_to_code(nationality)
            })

        response_data = {
            "season": season,
            "drivers": results
        }

        await cache_manager.set(cache_key, response_data, expire=600)
        return JSONResponse(response_data)
    
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)