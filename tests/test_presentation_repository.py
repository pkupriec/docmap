from __future__ import annotations

import json

from services.presentation.backend.repository import PresentationRepository


class DummyCursor:
    def __init__(self, rows=None) -> None:
        self.rows = list(rows or [])
        self.executed_sql: list[str] = []
        self.executed_params: list[object] = []
        self.description = [("value",)]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params=None) -> None:
        self.executed_sql.append(sql)
        self.executed_params.append(params)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class DummyConnection:
    def __init__(self, rows=None) -> None:
        self.cursor_instance = DummyCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


def test_resolve_location_for_documents_limits_alias_fallback(monkeypatch) -> None:
    conn = DummyConnection()
    monkeypatch.setattr("services.presentation.backend.repository.get_connection", lambda: conn)

    result = PresentationRepository().resolve_location_for_documents("00000000-0000-0000-0000-000000000001")

    assert result is None
    assert any("ranked_candidates AS (" in sql for sql in conn.cursor_instance.executed_sql)
    assert any("ROW_NUMBER() OVER" in sql for sql in conn.cursor_instance.executed_sql)
    assert any("r.location_rank = 'country'" in sql for sql in conn.cursor_instance.executed_sql)


def test_boundaries_query_requires_explicit_ids_and_deduplicates() -> None:
    feature = json.dumps(
        {
            "type": "Feature",
            "properties": {"location_id": "1", "location_name": "France", "location_rank": "country"},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]},
        }
    )
    conn = DummyConnection([(feature,), (feature,)])
    repo = PresentationRepository(lambda: conn)

    payload = repo.get_admin_boundaries_geojson(
        selected_location_id="00000000-0000-0000-0000-000000000010",
        highlighted_location_ids=["00000000-0000-0000-0000-000000000011"],
    )

    assert len(payload["features"]) == 1
    assert "location_id = ANY(%s::uuid[])" in conn.cursor_instance.executed_sql[-1]
    assert conn.cursor_instance.executed_params[-1] == [[
        "00000000-0000-0000-0000-000000000010",
        "00000000-0000-0000-0000-000000000011",
    ]]


def test_boundaries_without_explicit_ids_do_not_query_database() -> None:
    calls = 0

    def connect():
        nonlocal calls
        calls += 1
        return DummyConnection()

    payload = PresentationRepository(connect).get_admin_boundaries_geojson()

    assert payload == {"type": "FeatureCollection", "features": []}
    assert calls == 0


def test_pdf_range_uses_postgresql_substring() -> None:
    conn = DummyConnection([(b"%PDF",)])
    repo = PresentationRepository(lambda: conn)

    payload = repo.get_document_pdf_range(
        "00000000-0000-0000-0000-000000000101",
        start=0,
        length=4,
    )

    assert payload == b"%PDF"
    assert "SUBSTRING(ds.pdf_blob" in conn.cursor_instance.executed_sql[-1]
    assert conn.cursor_instance.executed_params[-1]["sql_start"] == 1
    assert conn.cursor_instance.executed_params[-1]["length"] == 4


def test_pdf_size_does_not_select_blob_payload() -> None:
    conn = DummyConnection([(9000,)])
    repo = PresentationRepository(lambda: conn)

    assert repo.get_document_pdf_size("00000000-0000-0000-0000-000000000101") == 9000
    sql = conn.cursor_instance.executed_sql[-1]
    assert "OCTET_LENGTH(ds.pdf_blob)" in sql
    assert "SELECT ds.pdf_blob" not in sql


def test_thumbnail_reads_only_thumbnail_blob() -> None:
    conn = DummyConnection([(b"RIFF-webp",)])
    repo = PresentationRepository(lambda: conn)

    assert repo.get_document_thumbnail("00000000-0000-0000-0000-000000000101") == b"RIFF-webp"
    sql = conn.cursor_instance.executed_sql[-1]
    assert "SELECT ds.pdf_thumbnail_webp" in sql
    assert "ds.pdf_blob" not in sql
