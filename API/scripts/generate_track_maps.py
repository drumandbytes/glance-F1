"""Pre-renders every current-season circuit's track-outline SVG into
API/static/track_maps/<circuitId>.svg, so API_Endpoints/map/router.py can
serve a static file on the request path instead of doing a live fastf1
telemetry load on every cold cache hit.

Run manually, or via .github/workflows/regenerate-track-maps.yml (monthly -
track layouts only ever change between seasons, so that's a safety margin,
not a cadence anything actually needs).

Needs TRACK_COLOUR set (same env var map_generator.py reads at request time).
"""
import os
import sys
from datetime import datetime

import fastf1
from fastf1.exceptions import RateLimitExceededError
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from API_Endpoints.map.router import generate_historical_track_map  # noqa: E402

# fastf1's default INFO level logs every fetch/parse step per driver -
# ~20 drivers x 24 circuits of "Loading data...", "Fetching...",
# "Position data is incomplete!" noise, none of it actionable here. Real
# failures still surface via the try/except below and the summary at the
# end - that's the signal that actually matters in this script's output.
fastf1.set_log_level("ERROR")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "track_maps")


def main():
    year = datetime.now().year
    resp = httpx.get(f"https://f1api.dev/api/{year}", timeout=30)
    resp.raise_for_status()
    calendar = resp.json()
    season = calendar.get("season")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    failures = []
    for race in calendar.get("races", []):
        circuit_id = (race.get("circuit") or {}).get("circuitId")
        if not circuit_id:
            continue

        print(f"{circuit_id}...", end=" ", flush=True)
        data = {"race": [race], "season": season}
        try:
            svg = generate_historical_track_map(data)
        except RateLimitExceededError as e:
            # Account-wide, not per-circuit - every remaining circuit would
            # fail identically, so stop instead of burning through the rest
            # of the calendar on guaranteed failures. Whatever's already
            # written stays; re-running later (next month, or by hand)
            # picks up from a warm fastf1 cache for the circuits that did
            # complete, so it isn't starting over.
            print(f"RATE LIMITED, stopping: {e}")
            failures.append(f"{circuit_id}: rate limited, {len(calendar.get('races', [])) - calendar.get('races', []).index(race) - 1} circuits not attempted")
            break
        except Exception as e:
            print(f"FAILED: {type(e).__name__}: {e}")
            failures.append(f"{circuit_id}: {type(e).__name__}: {e}")
            continue

        out_path = os.path.join(OUTPUT_DIR, f"{circuit_id}.svg")
        with open(out_path, "w") as f:
            f.write(svg)
        print(f"ok ({len(svg)} bytes)")

    if failures:
        print("\nFailed circuits (left as whatever was previously generated, if anything):")
        for f in failures:
            print(f"  {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
