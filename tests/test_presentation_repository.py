from __future__ import annotations

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
