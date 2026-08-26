from __future__ import annotations

import json
from pathlib import Path

import mapbox_vector_tile

from services.analytics import baked_geometry_assets
from services.analytics.baked_geometry_assets import build_baked_geometry_assets


class _DummyCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed_sql: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str) -> None:
        self.executed_sql.append(sql)

    def fetchall(self):
        return self.rows


class _DummyConn:
    def __init__(self, rows):
        self.cursor_instance = _DummyCursor(rows)

    def cursor(self) -> _DummyCursor:
        return self.cursor_instance


def test_simplify_geometry_keeps_full_precise_geometry_unchanged() -> None:
    geometry = {
        "type": "Polygon",
        "coordinates": [[[0.001, 0.001], [1.001, 0.001], [1.001, 1.001], [0.001, 0.001]]],
    }
    simplified = baked_geometry_assets._simplify_geometry(geometry, tolerance=0.0)
    assert simplified == geometry


def test_build_baked_geometry_assets_generates_all_modes_with_minimal_properties(tmp_path: Path) -> None:
    feature_a = {
        "type": "Feature",
        "properties": {
            "location_id": "00000000-0000-0000-0000-000000000001",
            "location_rank": "country",
            "location_name": "Testland",
            "country_name": "Testland",
            "region_name": None,
            "match_strategy": "rank_alias",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 0.0]]],
        },
    }
    feature_b = {
        "type": "Feature",
        "properties": {
            "location_id": "00000000-0000-0000-0000-000000000002",
            "location_rank": "admin_region",
            "location_name": "Test Region",
            "country_name": "Testland",
            "region_name": "Test Region",
            "extra_unused": "drop-me",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[40.0, 40.0], [48.0, 40.0], [48.0, 48.0], [40.0, 40.0]]],
        },
    }
    rows = [
        ("00000000-0000-0000-0000-000000000001", "country", feature_a),
        ("00000000-0000-0000-0000-000000000002", "admin_region", feature_b),
    ]
    conn = _DummyConn(rows)

    result = build_baked_geometry_assets(
        conn=conn,  # type: ignore[arg-type]
        assets_root=tmp_path / "presentation_geometry",
        zoom_min=0,
        zoom_max=1,
    )

    assert result.version.startswith("v1-")
    assert result.source_feature_count == 2
    assert set(result.modes.keys()) == {"full_precise", "balanced_precise", "simplified", "primitive"}
    assert all(mode.tile_count > 0 for mode in result.modes.values())
    assert result.manifest_path.exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["tile_format"] == "mvt_zxy_directory"
    assert manifest["source_table"] == "bi_admin_boundaries"
    assert set(manifest["modes"].keys()) == {"full_precise", "balanced_precise", "simplified", "primitive"}

    one_mode = result.modes["full_precise"]
    tile_file = next(one_mode.path.rglob("*.mvt"))
    decoded = mapbox_vector_tile.decode(tile_file.read_bytes(), default_options={"transformer": lambda x, y: (x, y)})
    layer = decoded["boundaries"]
    first_properties = layer["features"][0]["properties"]
    assert set(first_properties.keys()) == {"location_id", "location_rank", "location_name"}


def test_baked_geometry_version_is_deterministic_for_identical_input(tmp_path: Path) -> None:
    feature = {
        "type": "Feature",
        "properties": {
            "location_id": "00000000-0000-0000-0000-000000000001",
            "location_rank": "country",
            "location_name": "Stableland",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 0.0]]],
        },
    }
    rows = [("00000000-0000-0000-0000-000000000001", "country", feature)]

    first = build_baked_geometry_assets(
        conn=_DummyConn(rows),  # type: ignore[arg-type]
        assets_root=tmp_path / "first",
        zoom_min=0,
        zoom_max=0,
    )
    second = build_baked_geometry_assets(
        conn=_DummyConn(rows),  # type: ignore[arg-type]
        assets_root=tmp_path / "second",
        zoom_min=0,
        zoom_max=0,
    )

    assert first.version == second.version
