import httpx
import json
from datetime import datetime
from typing import Optional

ERGAST_BASE = "https://ergast.com/api/f1"
OPENF1_BASE = "https://api.openf1.org/v1"

_http_client: Optional[httpx.AsyncClient] = None


async def get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


async def close_http_client():
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None


async def fetch_driver_standings(season: int) -> dict:
    client = await get_http_client()
    url = f"{ERGAST_BASE}/{season}/driverStandings.json"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    return data.get("MRData", {}).get("StandingsTable", {}).get("StandingsList", [{}])[0]


async def fetch_constructor_standings(season: int) -> dict:
    client = await get_http_client()
    url = f"{ERGAST_BASE}/{season}/constructorStandings.json"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    return data.get("MRData", {}).get("StandingsTable", {}).get("StandingsList", [{}])[0]


async def fetch_race_results(season: int, round_num: int) -> tuple[dict, list]:
    client = await get_http_client()
    url = f"{ERGAST_BASE}/{season}/{round_num}/results.json"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races:
        return {}, []
    race = races[0]
    race_info = {
        "season": int(race.get("season", 0)),
        "round": int(race.get("round", 0)),
        "raceName": race.get("raceName", ""),
        "raceDate": race.get("date", ""),
    }
    results = race.get("Results", [])
    return race_info, results


async def fetch_season_schedule(season: int) -> list:
    client = await get_http_client()
    url = f"{ERGAST_BASE}/{season}.json"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    return data.get("MRData", {}).get("RaceTable", {}).get("Races", [])


async def fetch_openf1_sessions(year: int) -> list:
    client = await get_http_client()
    url = f"{OPENF1_BASE}/sessions?year={year}"
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


async def fetch_openf1_laps(session_key: int, driver_number: Optional[int] = None) -> list:
    client = await get_http_client()
    url = f"{OPENF1_BASE}/laps?session_key={session_key}"
    if driver_number:
        url += f"&driver_number={driver_number}"
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()
