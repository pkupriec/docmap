from __future__ import annotations

import json

from services.analytics import geometry_assets
from services.analytics.geometry_assets import GeometryTarget, build_admin_boundaries_asset


def _target(**overrides):
    base = {
        "location_id": "loc-1",
        "canonical_id": None,
        "location_name": "France",
        "location_rank": "country",
        "country_name": "France",
        "region_name": None,
        "document_count": 1,
        "osm_type": None,
        "osm_id": None,
        "osm_admin_level": None,
        "boundary_intent": False,
        "geocode_candidates": [],
        "osm_category": None,
        "osm_place_type": None,
        "canonical_resolution_method": None,
        "canonical_confidence": None,
    }
    base.update(overrides)
    return GeometryTarget(**base)


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
                            "location_rank": "admin_level_4",
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
            _target(location_id="country-1", location_name="France", location_rank="country", country_name="France"),
            _target(
                location_id="region-1",
                location_name="California",
                location_rank="admin_level_4",
                country_name="United States",
                region_name="California",
                osm_type="relation",
                osm_id=44,
            ),
            _target(
                location_id="ocean-1",
                location_name="Pacific Ocean",
                location_rank="ocean",
                country_name=None,
            ),
            _target(
                location_id="continent-1",
                location_name="Europe",
                location_rank="continent",
                country_name=None,
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
    out_payload = json.loads(output.read_text(encoding="utf-8"))
    assert {f["properties"]["location_id"] for f in out_payload["features"]} == {
        "country-1",
        "region-1",
        "ocean-1",
    }
    coverage_payload = json.loads(coverage.read_text(encoding="utf-8"))
    assert coverage_payload["totals"]["targets"] == 4
    assert coverage_payload["totals"]["matched_targets"] == 3
    assert coverage_payload["coverage_by_rank"]["admin_level_4"]["matched"] == 1
    assert coverage_payload["unmatched"]["continent"] == ["Europe"]
    assert conn.cursor_instance.truncated is True
    assert len(conn.cursor_instance.inserted) == 3


def test_dedupe_alias_targets_keeps_distinct_entities() -> None:
    targets = [
        _target(location_id="country-a", location_name="Congo"),
        _target(location_id="country-b", location_name="Congo"),
    ]
    deduped = geometry_assets._dedupe_alias_targets(targets)
    assert len(deduped) == 2
    assert {item.location_id for item in deduped} == {"country-a", "country-b"}


def test_select_feature_prefers_canonical_id_before_alias() -> None:
    feature = {
        "type": "Feature",
        "properties": {
            "canonical_id": "ne:country:FIN",
            "location_rank": "country",
            "location_name": "Finland",
            "safe_aliases": ["Finland"],
        },
        "geometry": {"type": "Polygon", "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]},
    }
    target = _target(
        location_id="loc-fin",
        canonical_id="ne:country:FIN",
        location_name="Suomi",
        country_name="Suomi",
        canonical_resolution_method="strict_alias",
        canonical_confidence=75,
    )
    by_location_id, by_canonical_id, by_osm, by_rank_alias, by_region_pair = geometry_assets._index_source_features([feature])

    matched, strategy = geometry_assets._select_feature_for_target(
        target,
        by_location_id=by_location_id,
        by_canonical_id=by_canonical_id,
        by_osm=by_osm,
        by_rank_alias=by_rank_alias,
        by_region_pair=by_region_pair,
    )

    assert matched is feature
    assert strategy == "canonical_id"

