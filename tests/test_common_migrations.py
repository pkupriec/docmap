from __future__ import annotations

from services.common import migrations


def test_runtime_schema_patches_include_phase19_geo_location_columns(monkeypatch) -> None:
    executed_sql: list[str] = []

    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql: str) -> None:
            executed_sql.append(sql)

    class DummyConn:
        autocommit = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self) -> DummyCursor:
            return DummyCursor()

    monkeypatch.setattr(migrations, "get_connection", lambda: DummyConn())

    migrations._apply_runtime_schema_patches()

    joined = "\n".join(executed_sql)
    assert "ADD COLUMN IF NOT EXISTS osm_admin_level INTEGER" in joined
    assert "ADD COLUMN IF NOT EXISTS boundary_intent BOOLEAN NOT NULL DEFAULT FALSE" in joined
    assert "ADD COLUMN IF NOT EXISTS geocode_candidates JSONB" in joined

