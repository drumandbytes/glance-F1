from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool
import httpx
import os
from fastapi_cache import FastAPICache

from .circuit_geometry import GEOJSON_CIRCUIT_IDS, fetch_circuit_geometry
from .map_generator import render_track_svg
from ..helpers.global_vars import NEXT_RACE_API_URL, default_expire

router = APIRouter()

# Pre-rendered by scripts/generate_track_maps.py, one file per known
# circuitId - see .github/workflows/regenerate-track-maps.yml (runs monthly,
# PRs whatever changed). Track layouts change rarely (once every few years,
# always between seasons), so this is the fast path for every normal
# request; live generation below only ever runs for a circuit that script
# hasn't covered yet (freshly added to GEOJSON_CIRCUIT_IDS since its last
# run).
STATIC_MAP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "track_maps")


def _generate(geojson_id, track_name):
    coordinates, geojson_name = fetch_circuit_geometry(geojson_id)
    return render_track_svg(coordinates, track_name or geojson_name)


@router.get("/", summary="Fetch next track map")
async def get_dynamic_track_map():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(NEXT_RACE_API_URL)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return PlainTextResponse(f"Failed to fetch race info: {str(e)}", status_code=502)

    race = data.get("race", [{}])[0]
    circuit = race.get("circuit") or {}
    circuit_id = circuit.get("circuitId")

    if circuit_id:
        static_path = os.path.join(STATIC_MAP_DIR, f"{circuit_id}.svg")
        if os.path.isfile(static_path):
            with open(static_path) as f:
                return Response(content=f.read(), media_type="image/svg+xml")

    geojson_id = GEOJSON_CIRCUIT_IDS.get(circuit_id)
    if not geojson_id:
        return PlainTextResponse(f"No track geometry known for circuit {circuit_id!r}", status_code=404)

    # Fallback: circuit not yet pre-rendered (e.g. added to
    # GEOJSON_CIRCUIT_IDS since the generator script's last monthly run).
    # Cached per-circuit so repeated dashboard refreshes before the next
    # scheduled run don't each re-fetch.
    cache = FastAPICache.get_backend()
    cache_key = f"track_map_svg:{circuit_id}"
    cached = await cache.get(cache_key)
    if cached:
        return Response(content=cached, media_type="image/svg+xml")

    try:
        # A static GeoJSON fetch + SVG render, not a live telemetry load -
        # fast, but still keep it off the event loop rather than assume so.
        svg_content = await run_in_threadpool(_generate, geojson_id, circuit.get("circuitName"))
    except Exception as e:
        return PlainTextResponse(str(e), status_code=500)

    await cache.set(cache_key, svg_content, expire=default_expire)
    return Response(content=svg_content, media_type="image/svg+xml")
