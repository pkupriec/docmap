from __future__ import annotations

import json

from services.presentation.backend.repository import PresentationRepository


class _DummyCursor:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []
        self.executed_params: list[object] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: object) -> None:
        self.executed_sql.append(sql)
        self.executed_params.append(params)

    def fetchone(self):
        return None


class _DummyConn:
    def __init__(self) -> None:
        self.cursor_instance = _DummyCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self) -> _DummyCursor:
        return self.cursor_instance


def test_resolve_location_for_documents_limits_fallback_ranks(monkeypatch) -> None:
    conn = _DummyConn()
    monkeypatch.setattr(
        "services.presentation.backend.repository.get_connection",
        lambda: conn,
    )

    repo = PresentationRepository()
    result = repo.resolve_location_for_documents("00000000-0000-0000-0000-000000000001")

    assert result is None
    assert conn.cursor_instance.executed_params[0] == {
        "location_id": "00000000-0000-0000-0000-000000000001",
    }
    sql = conn.cursor_instance.executed_sql[0] if conn.cursor_instance.executed_sql else ""
    assert "ranked_candidates AS (" in sql
    assert "scored_candidates AS (" in sql
    assert "ROW_NUMBER() OVER" in sql


def test_resolve_location_for_documents_includes_country_alias_fallback(monkeypatch) -> None:
    conn = _DummyConn()
    monkeypatch.setattr(
        "services.presentation.backend.repository.get_connection",
        lambda: conn,
    )

    repo = PresentationRepository()
    _ = repo.resolve_location_for_documents("00000000-0000-0000-0000-0000000000aa")

    sql = conn.cursor_instance.executed_sql[0] if conn.cursor_instance.executed_sql else ""
    assert "JOIN bi_locations peer" in sql
    assert "r.location_rank = 'country'" in sql
    assert "LOWER(COALESCE(peer.country, '')) = LOWER(COALESCE(r.country, ''))" in sql


class _BoundariesCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed_sql: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: object | None = None) -> None:
        self.executed_sql.append(sql)

    def fetchall(self):
        return self.rows


class _BoundariesConn:
    def __init__(self, rows):
        self.cursor_instance = _BoundariesCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


def test_boundaries_default_rank_filter_excludes_admin_levels(monkeypatch) -> None:
    rows = [
        (
            json.dumps(
                {
                    "type": "Feature",
                    "properties": {"location_id": "1", "location_name": "France", "location_rank": "country"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 0.0]]],
                    },
                }
            ),
        ),
        (
            json.dumps(
                {
                    "type": "Feature",
                    "properties": {
                        "location_id": "2",
                        "location_name": "California",
                        "location_rank": "admin_level_4",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[10.0, 10.0], [12.0, 10.0], [12.0, 12.0], [10.0, 10.0]]],
                    },
                }
            ),
        ),
    ]
    monkeypatch.setenv("DOCMAP_BOUNDARIES_LOW_ARTIFACT_PATH", "does-not-exist.geojson")
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: _BoundariesConn(rows))

    repo = PresentationRepository()
    payload = repo.get_admin_boundaries_geojson(minimal=True, rank_filter="default", geometry_detail="full")

    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["location_rank"] == "country"


def test_boundaries_low_detail_reduces_geometry_points(monkeypatch) -> None:
    ring = [[float(i), 0.0] for i in range(0, 24)] + [[0.0, 0.0]]
    rows = [
        (
            json.dumps(
                {
                    "type": "Feature",
                    "properties": {"location_id": "1", "location_name": "Region", "location_rank": "admin_region"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [ring],
                    },
                }
            ),
        ),
    ]
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: _BoundariesConn(rows))

    repo = PresentationRepository()
    full_payload = repo.get_admin_boundaries_geojson(minimal=False, rank_filter="all", geometry_detail="full")
    low_payload = repo.get_admin_boundaries_geojson(minimal=False, rank_filter="all", geometry_detail="low")

    full_ring = full_payload["features"][0]["geometry"]["coordinates"][0]
    low_ring = low_payload["features"][0]["geometry"]["coordinates"][0]
    assert len(low_ring) < len(full_ring)


def test_boundaries_minimal_payload_preserves_alias_metadata(monkeypatch) -> None:
    rows = [
        (
            json.dumps(
                {
                    "type": "Feature",
                    "properties": {
                        "location_id": "1",
                        "location_name": "Russia",
                        "location_rank": "country",
                        "safe_aliases": ["Russia", "Russian Federation"],
                        "country_aliases": ["Russia", "Russian Federation"],
                        "match_strategy": "rank_alias",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[30.0, 50.0], [31.0, 50.0], [31.0, 51.0], [30.0, 50.0]]],
                    },
                }
            ),
        ),
    ]
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: _BoundariesConn(rows))

    repo = PresentationRepository()
    payload = repo.get_admin_boundaries_geojson(minimal=True, rank_filter="all", geometry_detail="full")

    properties = payload["features"][0]["properties"]
    assert properties["location_name"] == "Russia"
    assert properties["safe_aliases"] == ["Russia", "Russian Federation"]
    assert properties["country_aliases"] == ["Russia", "Russian Federation"]
    assert properties["match_strategy"] == "rank_alias"
