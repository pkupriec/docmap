from services.analytics import service


def test_rebuild_analytics_orchestrates_builders(monkeypatch) -> None:
    class DummyConn:
        def __init__(self) -> None:
            self.committed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def commit(self) -> None:
            self.committed = True

    conn = DummyConn()

    monkeypatch.setattr(service, "get_connection", lambda: conn)
    monkeypatch.setattr(service, "build_bi_documents", lambda c: 10)
    monkeypatch.setattr(service, "build_bi_locations", lambda c: 5)
    monkeypatch.setattr(service, "build_bi_document_locations", lambda c: 12)
    monkeypatch.setattr(service, "build_bi_location_hierarchy", lambda c: 7)
    monkeypatch.setattr(service, "build_admin_boundaries_source", lambda c: 200)
    monkeypatch.setattr(
        service,
        "build_admin_boundaries_asset",
        lambda c: type("R", (), {"features_written": 3})(),
    )

    stats = service.rebuild_analytics()

    assert stats == {
        "bi_documents": 10,
        "bi_locations": 5,
        "bi_document_locations": 12,
        "bi_location_hierarchy": 7,
        "admin_boundaries_source": 200,
        "admin_boundaries": 3,
    }
    assert conn.committed is True


def test_build_bi_document_locations_rolls_up_mentions_to_parent_locations() -> None:
    class DummyCursor:
        def __init__(self) -> None:
            self.executed_sql: list[str] = []
            self.rowcount = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql: str) -> None:
            self.executed_sql.append(sql)
            if "INSERT INTO bi_document_locations" in sql:
                self.rowcount = 42

    class DummyConn:
        def __init__(self) -> None:
            self.cursor_instance = DummyCursor()

        def cursor(self) -> DummyCursor:
            return self.cursor_instance

    conn = DummyConn()

    rows = service.build_bi_document_locations(conn)  # type: ignore[arg-type]

    assert rows == 42
    assert any("TRUNCATE TABLE bi_document_locations" in sql for sql in conn.cursor_instance.executed_sql)
    insert_sql = next(sql for sql in conn.cursor_instance.executed_sql if "INSERT INTO bi_document_locations" in sql)
    assert "WITH RECURSIVE mention_rows AS" in insert_sql
    assert "WITH RECURSIVE" in insert_sql
    assert "rolled AS" in insert_sql
    assert "JOIN bi_locations parent ON parent.location_id = e.location_id" in insert_sql
    assert "parent.parent_location_id IS NOT NULL" in insert_sql
    assert "GROUP BY r.document_id, r.location_id" in insert_sql
