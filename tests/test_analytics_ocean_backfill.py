from __future__ import annotations

import json

from services.analytics.geometry_assets import backfill_merged_generic_ocean_boundaries


class _BackfillCursor:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.updates: list[tuple[object, ...]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params=None) -> None:
        if "SELECT location_id::text, feature_json" in sql:
            return
        if "UPDATE bi_admin_boundaries" in sql and params is not None:
            self.updates.append(tuple(params))

    def fetchall(self):
        return self.rows


class _BackfillConn:
    def __init__(self, rows) -> None:
        self.cursor_instance = _BackfillCursor(rows)

    def cursor(self):
        return self.cursor_instance


def test_backfill_merged_generic_ocean_boundaries_updates_generic_ocean_rows(tmp_path) -> None:
    source = tmp_path / "source.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "location_rank": "ocean",
                            "location_name": "Atlantic Ocean",
                            "aliases": ["Atlantic Ocean", "NORTH ATLANTIC OCEAN"],
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-40.0, 0.1], [-20.0, 0.1], [-20.0, 10.0], [-40.0, 0.1]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "location_rank": "ocean",
                            "location_name": "Atlantic Ocean",
                            "aliases": ["Atlantic Ocean", "SOUTH ATLANTIC OCEAN"],
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-30.0, -10.0], [-10.0, -10.0], [-10.0, -0.1], [-30.0, -10.0]]],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    existing_row = (
        "00000000-0000-0000-0000-000000000001",
        json.dumps(
            {
                "type": "Feature",
                "properties": {
                    "location_id": "00000000-0000-0000-0000-000000000001",
                    "location_rank": "ocean",
                    "location_name": "Atlantic Ocean",
                    "match_strategy": "rank_alias",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-40.0, 0.1], [-20.0, 0.1], [-20.0, 10.0], [-40.0, 0.1]]],
                },
            }
        ),
    )
    conn = _BackfillConn([existing_row])

    updated_rows = backfill_merged_generic_ocean_boundaries(conn, source_path=source)  # type: ignore[arg-type]

    assert updated_rows == 1
    assert len(conn.cursor_instance.updates) == 1
    updated_payload = json.loads(conn.cursor_instance.updates[0][0])
    assert updated_payload["geometry"]["type"] == "MultiPolygon"
    assert len(updated_payload["geometry"]["coordinates"]) == 2
    assert updated_payload["properties"]["match_strategy"] == "rank_alias_merged_backfill"
    assert conn.cursor_instance.updates[0][1:5] == (-40.0, -10.0, -10.0, 10.0)
