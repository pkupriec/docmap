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
                canonical_id=None,
                location_name="France",
                location_rank="country",
                country_name="France",
                region_name=None,
                document_count=10,
                osm_type=None,
                osm_id=None,
                canonical_resolution_method=None,
                canonical_confidence=None,
            ),
            GeometryTarget(
                location_id="region-1",
                canonical_id=None,
                location_name="California",
                location_rank="admin_region",
                country_name="United States",
                region_name="California",
                document_count=5,
                osm_type="relation",
                osm_id=44,
                canonical_resolution_method=None,
                canonical_confidence=None,
            ),
            GeometryTarget(
                location_id="ocean-1",
                canonical_id=None,
                location_name="Pacific Ocean",
                location_rank="ocean",
                country_name=None,
                region_name=None,
                document_count=1,
                osm_type=None,
                osm_id=None,
                canonical_resolution_method=None,
                canonical_confidence=None,
            ),
            GeometryTarget(
                location_id="continent-1",
                canonical_id=None,
                location_name="Europe",
                location_rank="continent",
                country_name=None,
                region_name=None,
                document_count=0,
                osm_type=None,
                osm_id=None,
                canonical_resolution_method=None,
                canonical_confidence=None,
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


def test_dedupe_alias_targets_prefers_osm_identity_and_docs() -> None:
    targets = [
        GeometryTarget(
            location_id="country-empty",
            canonical_id=None,
            location_name="Russian Federation",
            location_rank="country",
            country_name="Россия",
            region_name=None,
            document_count=0,
            osm_type=None,
            osm_id=None,
            canonical_resolution_method=None,
            canonical_confidence=None,
        ),
        GeometryTarget(
            location_id="country-docs",
            canonical_id=None,
            location_name="Russia",
            location_rank="country",
            country_name="Россия",
            region_name=None,
            document_count=187,
            osm_type="relation",
            osm_id=60189,
            canonical_resolution_method=None,
            canonical_confidence=None,
        ),
    ]

    deduped = geometry_assets._dedupe_alias_targets(targets)

    assert len(deduped) == 1
    assert deduped[0].location_id == "country-docs"


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
    target = GeometryTarget(
        location_id="loc-fin",
        canonical_id="ne:country:FIN",
        location_name="Suomi",
        location_rank="country",
        country_name="Suomi",
        region_name=None,
        document_count=23,
        osm_type=None,
        osm_id=None,
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


def test_dedupe_alias_targets_prefers_canonical_resolved_over_unresolved_high_docs() -> None:
    targets = [
        GeometryTarget(
            location_id="country-congo-unresolved",
            canonical_id=None,
            location_name="Congo",
            location_rank="country",
            country_name="Congo",
            region_name=None,
            document_count=50,
            osm_type=None,
            osm_id=None,
            canonical_resolution_method="ambiguous_alias_insufficient_signal",
            canonical_confidence=0,
        ),
        GeometryTarget(
            location_id="country-congo-cod",
            canonical_id="ne:country:COD",
            location_name="Congo",
            location_rank="country",
            country_name="Congo",
            region_name=None,
            document_count=7,
            osm_type=None,
            osm_id=None,
            canonical_resolution_method="deterministic_ambiguity_resolver",
            canonical_confidence=90,
        ),
    ]

    deduped = geometry_assets._dedupe_alias_targets(targets)

    assert len(deduped) == 1
    assert deduped[0].location_id == "country-congo-cod"
