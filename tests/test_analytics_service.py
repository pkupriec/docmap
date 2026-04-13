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

    conns: list[DummyConn] = []

    def _get_connection() -> DummyConn:
        conn = DummyConn()
        conns.append(conn)
        return conn

    monkeypatch.setattr(service, "get_connection", _get_connection)
    monkeypatch.setattr(service, "build_bi_documents", lambda c: 10)
    monkeypatch.setattr(service, "build_bi_locations", lambda c: 5)
    monkeypatch.setattr(service, "build_bi_document_locations", lambda c: 12)
    monkeypatch.setattr(service, "build_bi_location_hierarchy", lambda c: 7)
    monkeypatch.setattr(service, "build_admin_boundaries_source", lambda c: 200)
    monkeypatch.setattr(
        service,
        "build_admin_boundaries_asset",
        lambda c, **kwargs: type("R", (), {"features_written": 3})(),
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
    assert len(conns) == len(service.ANALYTICS_STEP_NAMES)
    assert all(conn.committed for conn in conns)


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


def test_build_bi_location_hierarchy_includes_continent_rollups() -> None:
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
            if "INSERT INTO bi_location_hierarchy" in sql:
                self.rowcount = 77

    class DummyConn:
        def __init__(self) -> None:
            self.cursor_instance = DummyCursor()

        def cursor(self) -> DummyCursor:
            return self.cursor_instance

    conn = DummyConn()

    rows = service.build_bi_location_hierarchy(conn)  # type: ignore[arg-type]

    assert rows == 77
    assert any("TRUNCATE TABLE bi_location_hierarchy" in sql for sql in conn.cursor_instance.executed_sql)
    insert_sql = next(sql for sql in conn.cursor_instance.executed_sql if "INSERT INTO bi_location_hierarchy" in sql)
    assert "continent_country AS (" in insert_sql
    assert "boundary_nodes AS (" in insert_sql
    assert "spatial_admin_seed AS (" in insert_sql
    assert "descendant.location_rank LIKE 'admin_level_%'" in insert_sql
    assert "descendant.location_rank = 'national_park'" in insert_sql
    assert "descendant.location_rank = 'desert'" in insert_sql
    assert "spatial_admin_expanded AS (" in insert_sql
    assert "ST_Intersects(" in insert_sql
    assert "ST_Area(ST_Intersection" in insert_sql
    assert "ST_GeomFromGeoJSON" in insert_sql
    assert "all_dedup AS (" in insert_sql


def test_coerce_bi_location_rank_uses_precision_for_country_when_rank_missing() -> None:
    assert (
        service._coerce_bi_location_rank(
            location_rank=None,
            precision="country",
            city=None,
            region=None,
            country="Democratic Republic of the Congo",
        )
        == "country"
    )


def test_coerce_bi_location_rank_preserves_national_park_for_admin_precision() -> None:
    assert (
        service._coerce_bi_location_rank(
            location_rank="national_park",
            precision="admin_region",
            city=None,
            region="Sankuru",
            country="République démocratique du Congo",
        )
        == "national_park"
    )


def test_rebuild_analytics_reports_admin_boundaries_detail_progress(monkeypatch) -> None:
    class DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def commit(self) -> None:
            return None

    monkeypatch.setattr(service, "get_connection", lambda: DummyConn())
    monkeypatch.setattr(service, "build_bi_documents", lambda c: 1)
    monkeypatch.setattr(service, "build_bi_locations", lambda c: 1)
    monkeypatch.setattr(service, "build_bi_document_locations", lambda c: 1)
    monkeypatch.setattr(service, "build_bi_location_hierarchy", lambda c: 1)
    monkeypatch.setattr(service, "build_admin_boundaries_source", lambda c: 1)

    def _build_admin_boundaries(_conn, *, on_target_progress=None, **_kwargs):
        if on_target_progress:
            on_target_progress(0, 4)
            on_target_progress(4, 4)
        return type("R", (), {"features_written": 2})()

    monkeypatch.setattr(service, "build_admin_boundaries_asset", _build_admin_boundaries)

    detail_events: list[tuple[str, int, int]] = []
    stats = service.rebuild_analytics(on_detail=lambda name, done, total: detail_events.append((name, done, total)))

    assert stats["admin_boundaries"] == 2
    assert ("admin_boundaries", 0, 4) in detail_events
    assert ("admin_boundaries", 4, 4) in detail_events
