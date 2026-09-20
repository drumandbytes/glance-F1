"""Season schedule, sourced from fastf1's own event schedule rather than
f1api.dev - it's the only source that correctly models Sprint Qualifying as
its own session (Ergast's classic schema predates that format and has no
field for it at all), and current_race_cleaner.py already found a real bug
in f1api.dev's round numbering it had to hand-patch around. One less
external dependency, one fewer thing that can silently drift wrong.

fastf1's schedule has no circuitId equivalent, unlike f1api.dev/Ergast -
CIRCUIT_IDS below is a static table instead of a second live API call per
lookup (every extra call eats into the same 500-calls/hour budget the map
generator already blew through once). Circuits are added to the calendar
at most once or twice a season; add new ones here when that happens.
"""
import fastf1

# (Location, Country) as fastf1's own schedule reports them -> circuitId, in
# the same slug convention scripts/generate_track_maps.py writes static SVGs
# under. Built by joining fastf1's 2025+2026 schedules against Ergast's
# get_race_schedule() by round number (matching on Location/Country string
# directly doesn't work - the two sources spell some of them differently,
# e.g. Ergast's "Montreal" vs fastf1's "Montréal"). Multiple entries per
# circuit are intentional: fastf1's own Location/Country strings for the
# same physical circuit have already been observed to drift between
# seasons (2025 "Yas Island" vs 2026 "Yas Marina", "Monaco" vs "Monte
# Carlo") - not a typo, both are real, keep both when it happens again.
# 2026's Malaysia entry reports Country "Bahrain" in fastf1's own schedule
# (a real upstream data quirk, not ours to fix) - included as-is because
# that's what a live lookup will actually see.
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

# fastf1's 5 generic session slots are named per event; map the name to the
# fixed keys the rest of this app (and the Glance dashboard's own template)
# already expects. "Sprint Shootout" was F1's 2023-only name for what's now
# called Sprint Qualifying - kept for older-season lookups.
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


def _row_to_race(row):
    schedule = {key: dict(_EMPTY_SESSION) for key in _SESSION_NAME_TO_KEY.values()}
    for i in range(1, 6):
        name = row.get(f"Session{i}")
        key = _SESSION_NAME_TO_KEY.get(name)
        if key:
            schedule[key] = _session_dict(row.get(f"Session{i}DateUtc"))

    circuit_id = CIRCUIT_IDS.get((row["Location"], row["Country"]))

    return {
        "round": int(row["RoundNumber"]),
        "raceName": row["EventName"],
        "url": None,  # fastf1's schedule carries no wiki link, unlike f1api.dev/Ergast
        "schedule": schedule,
        "circuit": {
            "circuitId": circuit_id,
            "circuitName": row["OfficialEventName"] or row["EventName"],
            "url": None,
            "country": row["Country"],
            "city": row["Location"],
        },
    }


def get_season_schedule(year: int) -> list[dict]:
    """Every points-paying race in `year`'s calendar, shaped like the old
    f1api.dev response (round/raceName/url/schedule/circuit), for
    current_race_cleaner.py and scripts/generate_track_maps.py to share.
    """
    sched = fastf1.get_event_schedule(year, include_testing=False)
    return [_row_to_race(row) for _, row in sched.iterrows()]
