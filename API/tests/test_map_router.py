import httpx
import pytest

import API_Endpoints.map.circuit_geometry as circuit_geometry
import API_Endpoints.map.router as router_module
from API_Endpoints.map.map_generator import render_track_svg


# A closed square in [lon, lat] order - not a real track, just simple enough
# to reason about bounding box/centering by hand.
_SQUARE_COORDINATES = [
    [10.0, 50.0],
    [10.001, 50.0],
    [10.001, 50.001],
    [10.0, 50.001],
    [10.0, 50.0],
]


def test_render_track_svg_rejects_invalid_track_colour(monkeypatch):
    monkeypatch.setenv("TRACK_COLOUR", "not-a-colour")
    with pytest.raises(ValueError):
        render_track_svg(_SQUARE_COORDINATES, "Test Circuit")


def test_render_track_svg_rejects_empty_coordinates():
    with pytest.raises(ValueError):
        render_track_svg([], "Test Circuit")


def test_render_track_svg_produces_valid_svg_with_track_name():
    svg = render_track_svg(_SQUARE_COORDINATES, "Test Circuit")

    assert "<svg" in svg
    assert "Test Circuit" in svg
    # TRACK_COLOUR is set by conftest.py to #e5d486
    assert "#e5d486" in svg


def test_geojson_circuit_ids_cover_every_schedule_circuit_id():
    # Both tables key off the same circuitId slugs - schedule.py's
    # CIRCUIT_IDS for current-season lookups, this one for fetching track
    # geometry. Every slug the app can ever produce must have geometry.
    from API_Endpoints.helpers.schedule import CIRCUIT_IDS

    schedule_slugs = set(CIRCUIT_IDS.values())
    geometry_slugs = set(circuit_geometry.GEOJSON_CIRCUIT_IDS.keys())

    missing = schedule_slugs - geometry_slugs
    assert not missing, f"circuitIds with no known track geometry: {missing}"


async def test_dynamic_track_map_serves_static_file_when_present(monkeypatch, tmp_path):
    static_dir = tmp_path / "track_maps"
    static_dir.mkdir()
    (static_dir / "monaco.svg").write_text("<svg>static monaco</svg>")
    monkeypatch.setattr(router_module, "STATIC_MAP_DIR", str(static_dir))

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"race": [{"circuit": {"circuitId": "monaco"}}]}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda: FakeAsyncClient())

    result = await router_module.get_dynamic_track_map()

    assert result.body == b"<svg>static monaco</svg>"


async def test_dynamic_track_map_generates_live_when_not_pre_rendered(monkeypatch, tmp_path):
    static_dir = tmp_path / "track_maps"
    static_dir.mkdir()
    monkeypatch.setattr(router_module, "STATIC_MAP_DIR", str(static_dir))

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"race": [{"circuit": {"circuitId": "monaco", "circuitName": "Circuit de Monaco"}}]}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda: FakeAsyncClient())

    def fake_fetch_circuit_geometry(geojson_id):
        assert geojson_id == circuit_geometry.GEOJSON_CIRCUIT_IDS["monaco"]
        return _SQUARE_COORDINATES, "Circuit de Monaco (geojson name)"

    monkeypatch.setattr(router_module, "fetch_circuit_geometry", fake_fetch_circuit_geometry)

    result = await router_module.get_dynamic_track_map()

    assert b"<svg" in result.body
    assert b"Circuit de Monaco" in result.body


async def test_dynamic_track_map_404s_for_unknown_circuit(monkeypatch, tmp_path):
    static_dir = tmp_path / "track_maps"
    static_dir.mkdir()
    monkeypatch.setattr(router_module, "STATIC_MAP_DIR", str(static_dir))

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"race": [{"circuit": {"circuitId": "totally_unknown_circuit"}}]}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda: FakeAsyncClient())

    result = await router_module.get_dynamic_track_map()

    assert result.status_code == 404
