from datetime import datetime

import pytz
from ..data_sources import fetch_season_schedule

CIRCUIT_IDS = {
    ("Melbourne", "Australia"): "albert_park",
    ("Shanghai", "China"): "shanghai",
    ("Suzuka", "Japan"): "suzuka",
    ("Sakhir", "Bahrain"): "bahrain",
    ("Jeddah", "Saudi Arabia"): "jeddah",
    ("Miami Gardens", "United States"): "miami",
    ("Imola", "Italy"): "imola",
    ("Monaco", "Monaco"): "monaco",
    ("Monte Carlo", "Monaco"): "monaco",
    ("Barcelona", "Spain"): "catalunya",
    ("Montréal", "Canada"): "villeneuve",
    ("Spielberg", "Austria"): "red_bull_ring",
    ("Silverstone", "United Kingdom"): "silverstone",
    ("Spa-Francorchamps", "Belgium"): "spa",
    ("Budapest", "Hungary"): "hungaroring",
    ("Zandvoort", "Netherlands"): "zandvoort",
    ("Monza", "Italy"): "monza",
    ("Madrid", "Spain"): "madring",
    ("Baku", "Azerbaijan"): "baku",
    ("Kuala Lumpur", "Malaysia"): "sepang",
    ("Kuala Lumpur", "Bahrain"): "sepang",
    ("Marina Bay", "Singapore"): "marina_bay",
    ("Austin", "United States"): "americas",
    ("Mexico City", "Mexico"): "rodriguez",
    ("São Paulo", "Brazil"): "interlagos",
    ("Las Vegas", "United States"): "vegas",
    ("Lusail", "Qatar"): "losail",
    ("Yas Island", "United Arab Emirates"): "yas_marina",
    ("Yas Marina", "United Arab Emirates"): "yas_marina",
}

_SESSION_NAME_TO_KEY = {
    "Practice 1": "fp1",
    "Practice 2": "fp2",
    "Practice 3": "fp3",
    "Qualifying": "qualy",
    "Sprint Qualifying": "sprintQualy",
    "Sprint Shootout": "sprintQualy",
    "Sprint": "sprintRace",
    "Race": "race",
}

_EMPTY_SESSION = {"date": None, "time": None}


def _session_dict(dt):
    if dt is None or str(dt) == "NaT":
        return dict(_EMPTY_SESSION)
    return {"date": dt.strftime("%Y-%m-%d"), "time": dt.strftime("%H:%M:%SZ")}


async def get_season_schedule(year: int) -> list[dict]:
    """Fetch season schedule from Ergast (still the most reliable for schedules)."""
    races = await fetch_season_schedule(year)
    
    result = []
    for idx, race in enumerate(races, start=1):
        race_obj = _ergast_race_to_race(race, idx)
        result.append(race_obj)
    
    return result


def _ergast_race_to_race(race_data: dict, round_number: int) -> dict:
    """Convert Ergast race format to our internal format."""
    schedule = {key: dict(_EMPTY_SESSION) for key in _SESSION_NAME_TO_KEY.values()}
    
    date_str = race_data.get("date", "")
    time_str = race_data.get("time", "")
    
    schedule["race"] = {
        "date": date_str,
        "time": time_str,
    }
    
    fp1 = race_data.get("FirstPractice", {})
    if fp1 and fp1.get("date") and fp1.get("time"):
        dt = datetime.fromisoformat(f"{fp1['date']}T{fp1['time']}".replace("Z", "+00:00"))
        schedule["fp1"] = {
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%SZ")
        }
    
    fp2 = race_data.get("SecondPractice", {})
    if fp2 and fp2.get("date") and fp2.get("time"):
        dt = datetime.fromisoformat(f"{fp2['date']}T{fp2['time']}".replace("Z", "+00:00"))
        schedule["fp2"] = {
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%SZ")
        }
    
    fp3 = race_data.get("ThirdPractice", {})
    if fp3 and fp3.get("date") and fp3.get("time"):
        dt = datetime.fromisoformat(f"{fp3['date']}T{fp3['time']}".replace("Z", "+00:00"))
        schedule["fp3"] = {
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%SZ")
        }
    
    qualy = race_data.get("Qualifying", {})
    if qualy and qualy.get("date") and qualy.get("time"):
        dt = datetime.fromisoformat(f"{qualy['date']}T{qualy['time']}".replace("Z", "+00:00"))
        schedule["qualy"] = {
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%SZ")
        }
    
    sprint = race_data.get("Sprint", {})
    if sprint and sprint.get("date") and sprint.get("time"):
        dt = datetime.fromisoformat(f"{sprint['date']}T{sprint['time']}".replace("Z", "+00:00"))
        schedule["sprintRace"] = {
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%SZ")
        }
    
    circuit = race_data.get("Circuit", {})
    location = circuit.get("Location", {})
    country = location.get("country", "")
    circuit_name = circuit.get("circuitName", "")
    circuit_id = CIRCUIT_IDS.get((location.get("locality", ""), country))
    
    return {
        "round": round_number,
        "raceName": race_data.get("raceName", ""),
        "url": circuit.get("url"),
        "schedule": schedule,
        "circuit": {
            "circuitId": circuit_id,
            "circuitName": circuit_name,
            "url": circuit.get("url"),
            "country": country,
            "city": location.get("locality", ""),
        },
    }


def parse_session_datetime(session_data: dict):
    """UTC-aware datetime for a single {date, time} schedule entry."""
    date_str = session_data.get("date")
    time_str = session_data.get("time")
    if not date_str or not time_str:
        return None
    dt = datetime.strptime(f"{date_str}T{time_str}", "%Y-%m-%dT%H:%M:%SZ")
    return pytz.utc.localize(dt)


def find_current_race(races: list[dict], now) -> dict | None:
    """Find the first race whose race session hasn't started yet."""
    races = sorted(races, key=lambda r: r.get("schedule", {}).get("race", {}).get("date") or "")
    for race in races:
        race_dt = parse_session_datetime(race.get("schedule", {}).get("race", {}))
        if race_dt and race_dt >= now:
            return race
    return None

