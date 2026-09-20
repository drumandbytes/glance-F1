"""Pre-renders every known circuit's track-outline SVG into
API/static/track_maps/<circuitId>.svg from bacinger/f1-circuits' static
GeoJSON dataset, so API_Endpoints/map/router.py can serve a static file on
the request path with no live lookup at all.

Run manually, or via .github/workflows/regenerate-track-maps.yml (monthly -
track layouts only ever change between seasons, and the source dataset
itself changes rarely, so that's a safety margin, not a cadence anything
actually needs).

Needs TRACK_COLOUR set (same env var map_generator.py reads at request time).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from API_Endpoints.map.circuit_geometry import GEOJSON_CIRCUIT_IDS, fetch_circuit_geometry  # noqa: E402
from API_Endpoints.map.map_generator import render_track_svg  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "track_maps")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    failures = []
    for circuit_id, geojson_id in GEOJSON_CIRCUIT_IDS.items():
        print(f"{circuit_id}...", end=" ", flush=True)
        try:
            coordinates, track_name = fetch_circuit_geometry(geojson_id)
            svg = render_track_svg(coordinates, track_name)
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
