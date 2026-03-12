from __future__ import annotations

import json

from services.analytics.geometry_assets import build_admin_boundaries_asset


class _DummyCursor:
    def __init__(self, country_rows, region_rows) -> None:
        self._country_rows = country_rows
        self._region_rows = region_rows
        self._last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str) -> None:
        self._last_sql = sql

    def fetchall(self):
        if "GROUP BY LOWER(TRIM(bl.country))" in self._last_sql and "bl.region" not in self._last_sql:
            return self._country_rows
        return self._region_rows


class _DummyConn:
    def __init__(self, country_rows, region_rows) -> None:
        self._country_rows = country_rows
        self._region_rows = region_rows

    def cursor(self):
        return _DummyCursor(self._country_rows, self._region_rows)


def test_build_admin_boundaries_asset_generates_geojson_and_coverage(tmp_path) -> None:
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
                        "properties": {"location_rank": "country", "location_name": "France"},
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
                        },
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": [[[[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 0.0]]]],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    conn = _DummyConn(
        country_rows=[("france", "France"), ("germany", "Germany")],
        region_rows=[("united states", "United States", "california", "California")],
    )

    result = build_admin_boundaries_asset(
        conn,
        source_path=source,
        output_path=output,
        coverage_path=coverage,
    )

    assert result.features_written == 2
    assert output.exists()
    assert coverage.exists()

    out_payload = json.loads(output.read_text(encoding="utf-8"))
    assert out_payload["type"] == "FeatureCollection"
    assert len(out_payload["features"]) == 2
    assert {"country", "region"} == {f["properties"]["location_rank"] for f in out_payload["features"]}

    coverage_payload = json.loads(coverage.read_text(encoding="utf-8"))
    assert coverage_payload["totals"]["matched_countries"] == 1
    assert coverage_payload["totals"]["matched_regions"] == 1
    assert coverage_payload["unmatched"]["countries"] == ["Germany"]
