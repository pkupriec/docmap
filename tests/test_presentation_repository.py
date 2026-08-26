from __future__ import annotations

import json
from pathlib import Path

from services.presentation.backend.repository import PresentationRepository, parse_boundary_chunk, parse_viewport_bucket


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
    sql = conn.cursor_instance.executed_sql[-1] if conn.cursor_instance.executed_sql else ""
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

    sql = conn.cursor_instance.executed_sql[-1] if conn.cursor_instance.executed_sql else ""
    assert "JOIN bi_locations peer" in sql
    assert "r.location_rank = 'country'" in sql
    assert "LOWER(COALESCE(peer.country, '')) = LOWER(COALESCE(r.country, ''))" in sql


class _BoundariesCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed_sql: list[str] = []
        self.executed_params: list[object | None] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: object | None = None) -> None:
        self.executed_sql.append(sql)
        self.executed_params.append(params)

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


def test_boundaries_default_rank_filter_is_pushed_to_sql(monkeypatch) -> None:
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
    conn = _BoundariesConn(rows)
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: conn)

    repo = PresentationRepository()
    payload = repo.get_admin_boundaries_geojson(minimal=True, rank_filter="default")

    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 2
    assert conn.cursor_instance.executed_params[-1] == [["city", "admin_region", "country", "continent", "ocean"]]


def test_boundaries_default_rank_filter_uses_canonical_rank_list(monkeypatch) -> None:
    conn = _BoundariesConn([])
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: conn)

    repo = PresentationRepository()
    payload = repo.get_admin_boundaries_geojson(minimal=True, rank_filter="default")

    assert payload["features"] == []
    params = conn.cursor_instance.executed_params[-1]
    assert params == [["city", "admin_region", "country", "continent", "ocean"]]


def test_boundaries_request_normalizes_region_rank_alias(monkeypatch) -> None:
    conn = _BoundariesConn([])
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: conn)

    repo = PresentationRepository()
    _ = repo.get_admin_boundaries_geojson(minimal=True, rank_filter="all", ranks=("region", "country", "city"))

    params = conn.cursor_instance.executed_params[-1]
    assert params == [["country", "admin_region", "city"]]


def test_parse_viewport_bucket_normalizes_to_canonical_identity() -> None:
    bucket = parse_viewport_bucket("regional:-20:-24:40:36")

    assert bucket.bucket_id == "regional:-20:-24:40:36"
    assert bucket.band == "regional"
    assert bucket.bbox == (-20.0, -24.0, 40.0, 36.0)


def test_parse_boundary_chunk_normalizes_to_canonical_identity() -> None:
    chunk = parse_boundary_chunk("regional:2:4")

    assert chunk.chunk_id == "regional:2:4"
    assert chunk.band == "regional"
    assert chunk.column == 2
    assert chunk.row == 4
    assert chunk.bbox == (-140.0, -42.0, -120.0, -30.0)


def test_boundaries_bbox_filter_and_explicit_ids_are_pushed_to_sql(monkeypatch) -> None:
    conn = _BoundariesConn([])
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: conn)

    repo = PresentationRepository()
    _ = repo.get_admin_boundaries_geojson(
        minimal=True,
        rank_filter="all",
        ranks=("country", "admin_region"),
        bbox=(170.0, -10.0, -170.0, 15.0),
        selected_location_id="00000000-0000-0000-0000-000000000010",
        highlighted_location_ids=(
            "00000000-0000-0000-0000-000000000012",
            "00000000-0000-0000-0000-000000000011",
        ),
    )

    sql = conn.cursor_instance.executed_sql[-1]
    params = conn.cursor_instance.executed_params[-1]
    assert "max_lat >= %s AND min_lat <= %s" in sql
    assert "(max_lon >= %s) OR (min_lon <= %s)" in sql
    assert "location_id = ANY(%s::uuid[])" in sql
    assert params == [
        ["country", "admin_region"],
        -10.0,
        15.0,
        170.0,
        -170.0,
        [
            "00000000-0000-0000-0000-000000000010",
            "00000000-0000-0000-0000-000000000011",
            "00000000-0000-0000-0000-000000000012",
        ],
    ]


def test_boundaries_viewport_bucket_filter_is_pushed_to_sql(monkeypatch) -> None:
    conn = _BoundariesConn([])
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: conn)

    repo = PresentationRepository()
    _ = repo.get_admin_boundaries_geojson(
        minimal=True,
        rank_filter="all",
        ranks=("country", "admin_region"),
        viewport_bucket="regional:-20:-24:40:36",
        selected_location_id="00000000-0000-0000-0000-000000000010",
        highlighted_location_ids=(
            "00000000-0000-0000-0000-000000000012",
            "00000000-0000-0000-0000-000000000011",
        ),
    )

    sql = conn.cursor_instance.executed_sql[-1]
    params = conn.cursor_instance.executed_params[-1]
    assert "max_lat >= %s AND min_lat <= %s" in sql
    assert "max_lon >= %s AND min_lon <= %s" in sql
    assert "location_id = ANY(%s::uuid[])" in sql
    assert params == [
        ["country", "admin_region"],
        -24.0,
        36.0,
        -20.0,
        40.0,
        [
            "00000000-0000-0000-0000-000000000010",
            "00000000-0000-0000-0000-000000000011",
            "00000000-0000-0000-0000-000000000012",
        ],
    ]


def test_boundaries_chunk_ids_filter_is_pushed_to_sql(monkeypatch) -> None:
    conn = _BoundariesConn([])
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: conn)

    repo = PresentationRepository()
    _ = repo.get_admin_boundaries_geojson(
        minimal=True,
        rank_filter="all",
        ranks=("country", "admin_region"),
        chunk_ids=("regional:3:4", "regional:2:4"),
        selected_location_id="00000000-0000-0000-0000-000000000010",
        highlighted_location_ids=(
            "00000000-0000-0000-0000-000000000012",
            "00000000-0000-0000-0000-000000000011",
        ),
    )

    sql = conn.cursor_instance.executed_sql[-1]
    params = conn.cursor_instance.executed_params[-1]
    assert "max_lat >= %s AND min_lat <= %s" in sql
    assert "max_lon >= %s AND min_lon <= %s" in sql
    assert " OR " in sql
    assert "location_id = ANY(%s::uuid[])" in sql
    assert params == [
        ["country", "admin_region"],
        -42.0,
        -30.0,
        -140.0,
        -120.0,
        -42.0,
        -30.0,
        -120.0,
        -100.0,
        [
            "00000000-0000-0000-0000-000000000010",
            "00000000-0000-0000-0000-000000000011",
            "00000000-0000-0000-0000-000000000012",
        ],
    ]


def test_boundaries_explicit_ids_are_included_outside_bbox(monkeypatch) -> None:
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
    ]
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: _BoundariesConn(rows))

    repo = PresentationRepository()
    payload = repo.get_admin_boundaries_geojson(
        minimal=True,
        rank_filter="all",
        bbox=(-5.0, -5.0, 5.0, 5.0),
        selected_location_id="1",
    )

    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["location_id"] == "1"


def test_boundaries_explicit_ids_are_included_outside_viewport_bucket(monkeypatch) -> None:
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
    ]
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: _BoundariesConn(rows))

    repo = PresentationRepository()
    payload = repo.get_admin_boundaries_geojson(
        minimal=True,
        rank_filter="all",
        viewport_bucket="regional:-20:-24:40:36",
        selected_location_id="1",
    )

    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["location_id"] == "1"


def test_boundaries_explicit_ids_are_included_outside_chunk_ids(monkeypatch) -> None:
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
    ]
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: _BoundariesConn(rows))

    repo = PresentationRepository()
    payload = repo.get_admin_boundaries_geojson(
        minimal=True,
        rank_filter="all",
        chunk_ids=("regional:2:4",),
        selected_location_id="1",
    )

    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["location_id"] == "1"


def test_boundaries_deduplicate_duplicate_location_ids(monkeypatch) -> None:
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
                    "properties": {"location_id": "1", "location_name": "France", "location_rank": "country"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 0.0]]],
                    },
                }
            ),
        ),
    ]
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: _BoundariesConn(rows))

    repo = PresentationRepository()
    payload = repo.get_admin_boundaries_geojson(minimal=True, rank_filter="all")

    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["location_id"] == "1"


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
    payload = repo.get_admin_boundaries_geojson(minimal=True, rank_filter="all")

    properties = payload["features"][0]["properties"]
    assert properties["location_name"] == "Russia"
    assert properties["safe_aliases"] == ["Russia", "Russian Federation"]
    assert properties["country_aliases"] == ["Russia", "Russian Federation"]
    assert properties["match_strategy"] == "rank_alias"


def test_canonical_schema_includes_boundary_envelope_columns_and_indexes() -> None:
    schema = Path("database/schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE bi_admin_boundaries (" in schema
    assert "min_lon DOUBLE PRECISION" in schema
    assert "min_lat DOUBLE PRECISION" in schema
    assert "max_lon DOUBLE PRECISION" in schema
    assert "max_lat DOUBLE PRECISION" in schema
    assert "CREATE INDEX idx_bi_admin_boundaries_lat_bounds" in schema
    assert "CREATE INDEX idx_bi_admin_boundaries_lon_bounds" in schema
