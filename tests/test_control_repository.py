from __future__ import annotations

from services.control.repository import ControlRepository


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, query: str, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return [1]

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConn:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self, **kwargs):
        return self._cursor

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_progress_upsert_uses_current_state_conflict_key(monkeypatch) -> None:
    cur = FakeCursor()
    conn = FakeConn(cur)
    repo = ControlRepository()
    monkeypatch.setattr(repo, "_connect", lambda: conn)

    repo.upsert_progress(
        1,
        "crawl",
        current_index=1,
        total_items=10,
        items_completed=1,
        items_failed=0,
        message="m",
    )

    query = cur.executed[0][0]
    assert "ON CONFLICT (pipeline_run_id, stage_name)" in query


def test_logs_query_orders_by_id_ascending(monkeypatch) -> None:
    cur = FakeCursor()
    conn = FakeConn(cur)
    repo = ControlRepository()
    monkeypatch.setattr(repo, "_connect", lambda: conn)

    repo.list_logs(1, after_id=2, limit=200)

    query = cur.executed[0][0]
    assert "ORDER BY id ASC" in query
