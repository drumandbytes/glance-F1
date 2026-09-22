from datetime import datetime, timedelta
from starlette.responses import JSONResponse

from .data_sources import fetch_race_results
from .helpers.functions import country_to_code
from .helpers.global_vars import nationality_map, default_expire
from .helpers.time_functions import MT
from .cache import cache_manager

def format_time(total_race_time: str, is_winner: bool) -> str:
    if not total_race_time or total_race_time == "":
        return None
    
    try:
        total_seconds = float(total_race_time)
    except (ValueError, TypeError):
        return None
    
    if not is_winner:
        return f"+{total_seconds:.3f}"
    
    h, rem = divmod(int(total_seconds), 3600)
    m, s = divmod(rem, 60)
    ms = int(round((total_seconds - int(total_seconds)) * 1000))
    return f"{h}:{m:02d}:{s:02d}.{ms:03d}" if h else f"{m}:{s:02d}.{ms:03d}"

async def get_last_race(request):
    cache_key = "f1:last_race"
    cached = await cache_manager.get(cache_key)
    if cached:
        return JSONResponse(cached)

    try:
        race_info, results = await fetch_race_results("current", "last")
        
        if not race_info:
            return JSONResponse({"error": "Could not fetch last race"}, status_code=500)

        formatted_results = []
        for result in results:
            nationality = result.get("Driver", {}).get("nationality", "")
            if nationality in nationality_map:
                nationality = nationality_map[nationality]

            is_dnf = not str(result.get("position", "")).isdigit()
            surname = result.get("Driver", {}).get("familyName", "")

            if is_dnf:
                laps = result.get("laps", "")
                time_str = f"DNF ({laps})" if laps else "DNF"
            else:
                time_str = format_time(result.get("Time"), result.get("position") == "1")

            formatted_results.append({
                "position": result.get("position"),
                "surname": surname,
                "flag": country_to_code(nationality),
                "teamId": result.get("Constructor", {}).get("constructorId", ""),
                "time": time_str,
                "dnf_laps": int(result.get("laps", 0)) if is_dnf and result.get("laps") else None,
            })

        response_data = {
            "season": race_info.get("season"),
            "round": race_info.get("round"),
            "raceName": race_info.get("raceName"),
            "date": race_info.get("raceDate"),
            "cache_expires": (datetime.now(MT) + timedelta(days=1)).isoformat(),
            "results": formatted_results,
        }

        await cache_manager.set(cache_key, response_data, expire=default_expire)
        return JSONResponse(response_data)

    except Exception as e:
        return JSONResponse({"error": f"Exception while fetching: {e}"}, status_code=500)
