from __future__ import annotations

import json

from services.analytics import geometry_assets
from services.analytics.geometry_assets import GeometryTarget, build_admin_boundaries_asset


def test_build_admin_boundaries_asset_generates_location_id_keyed_geojson_and_coverage(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "source.geojson"
    output = tmp_path / "out.geojson"
    coverage = tmp_path / "coverage.json"

    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "location_id": "country-1",
                            "location_rank": "country",
                            "location_name": "France",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "location_rank": "region",
                            "location_name": "California",
                            "country_name": "United States",
                            "region_name": "California",
                            "osm_type": "relation",
                            "osm_id": 44,
                        },
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": [[[[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 0.0]]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "location_rank": "ocean",
                            "location_name": "Pacific Ocean",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[10.0, 10.0], [11.0, 10.0], [11.0, 11.0], [10.0, 10.0]]],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        geometry_assets,
        "_query_targets",
        lambda _conn: [
            GeometryTarget(
                location_id="country-1",
                location_name="France",
                location_rank="country",
                country_name="France",
                region_name=None,
                osm_type=None,
                osm_id=None,
            ),
            GeometryTarget(
                location_id="region-1",
                location_name="California",
                location_rank="admin_region",
                country_name="United States",
                region_name="California",
                osm_type="relation",
                osm_id=44,
            ),
            GeometryTarget(
                location_id="ocean-1",
                location_name="Pacific Ocean",
                location_rank="ocean",
                country_name=None,
                region_name=None,
                osm_type=None,
                osm_id=None,
            ),
            GeometryTarget(
                location_id="continent-1",
                location_name="Europe",
                location_rank="continent",
                country_name=None,
                region_name=None,
                osm_type=None,
                osm_id=None,
            ),
        ],
    )

    class DummyCursor:
        def __init__(self) -> None:
            self.inserted: list[tuple[str, str, str]] = []
            self.truncated = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql: str, *args, **kwargs) -> None:
            if "TRUNCATE TABLE bi_admin_boundaries" in sql:
                self.truncated = True

        def executemany(self, sql: str, rows) -> None:
            if "INSERT INTO bi_admin_boundaries" in sql:
                self.inserted.extend(list(rows))

    class DummyConn:
        def __init__(self) -> None:
            self.cursor_instance = DummyCursor()

        def cursor(self) -> DummyCursor:
            return self.cursor_instance

    conn = DummyConn()

    result = build_admin_boundaries_asset(
        conn=conn,  # type: ignore[arg-type]
        source_path=source,
        output_path=output,
        coverage_path=coverage,
    )

    assert result.features_written == 3
    assert output.exists()
    assert coverage.exists()

    out_payload = json.loads(output.read_text(encoding="utf-8"))
    assert out_payload["type"] == "FeatureCollection"
    assert len(out_payload["features"]) == 3
    assert {f["properties"]["location_id"] for f in out_payload["features"]} == {
        "country-1",
        "region-1",
        "ocean-1",
    }
    assert {f["properties"]["location_rank"] for f in out_payload["features"]} == {
        "country",
        "admin_region",
        "ocean",
    }

    coverage_payload = json.loads(coverage.read_text(encoding="utf-8"))
    assert coverage_payload["totals"]["targets"] == 4
    assert coverage_payload["totals"]["matched_targets"] == 3
    assert coverage_payload["coverage_by_rank"]["country"]["matched"] == 1
    assert coverage_payload["coverage_by_rank"]["admin_region"]["matched"] == 1
    assert coverage_payload["coverage_by_rank"]["ocean"]["matched"] == 1
    assert coverage_payload["coverage_by_rank"]["continent"]["matched"] == 0
    assert coverage_payload["unmatched"]["continent"] == ["Europe"]
    assert conn.cursor_instance.truncated is True
    assert len(conn.cursor_instance.inserted) == 3
    assert {row[0] for row in conn.cursor_instance.inserted} == {"country-1", "region-1", "ocean-1"}
