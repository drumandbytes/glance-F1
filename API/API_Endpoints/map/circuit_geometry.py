"""Static track-outline geometry from bacinger/f1-circuits
(https://github.com/bacinger/f1-circuits, MIT licensed) - a community-
maintained GeoJSON dataset of real circuit boundaries, built independently of
any F1 session ever having been driven. Track layouts are physically fixed,
so this needs no live-timing API and no rate limit - and unlike deriving a
track's outline from recorded session telemetry, it already has data for a
circuit before its first-ever F1 session (e.g. Madrid's 2026 debut).
"""
import httpx

GEOJSON_BASE_URL = "https://raw.githubusercontent.com/bacinger/f1-circuits/master/circuits"

# Our circuitId (matches schedule.py's CIRCUIT_IDS and the static SVG
# filenames) -> bacinger/f1-circuits' own <country-code>-<year-opened> id.
# Built by matching that repo's f1-locations.json against our own circuit
# list by location name. Update when a new circuit joins the calendar, same
# as CIRCUIT_IDS.
GEOJSON_CIRCUIT_IDS = {
    "albert_park": "au-1953",
    "shanghai": "cn-2004",
    "suzuka": "jp-1962",
    "bahrain": "bh-2002",
    "jeddah": "sa-2021",
    "miami": "us-2022",
    "imola": "it-1953",
    "monaco": "mc-1929",
    "catalunya": "es-1991",
    "villeneuve": "ca-1978",
    "red_bull_ring": "at-1969",
    "silverstone": "gb-1948",
    "spa": "be-1925",
    "hungaroring": "hu-1986",
    "zandvoort": "nl-1948",
    "monza": "it-1922",
    "madring": "es-2026",
    "baku": "az-2016",
    "sepang": "my-1999",
    "marina_bay": "sg-2008",
    "americas": "us-2012",
    "rodriguez": "mx-1962",
    "interlagos": "br-1940",
    "vegas": "us-2023",
    "losail": "qa-2004",
    "yas_marina": "ae-2009",
}


def fetch_circuit_geometry(geojson_id: str) -> tuple[list, str]:
    """Returns ([lon, lat] pairs, circuit name) for the given geojson id."""
    resp = httpx.get(f"{GEOJSON_BASE_URL}/{geojson_id}.geojson", timeout=10)
    resp.raise_for_status()
    feature = resp.json()["features"][0]
    return feature["geometry"]["coordinates"], feature["properties"].get("Name")
