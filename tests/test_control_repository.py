from __future__ import annotations

from services.control.repository import ControlRepository


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple | None]] = []
        self.rowcount = 1

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

    def transaction(self):
        return self

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


def test_poll_next_command_atomically_claims_with_expiring_lease(monkeypatch) -> None:
    cur = FakeCursor()
    conn = FakeConn(cur)
    repo = ControlRepository()
    monkeypatch.setattr(repo, "_connect", lambda: conn)

    repo.poll_next_command(lease_seconds=45)

    query, params = cur.executed[0]
    assert "FOR UPDATE SKIP LOCKED" in query
    assert "lease_expires_at <= NOW()" in query
    assert "UPDATE pipeline_commands AS command" in query
    assert params is not None and params[1] == 45


def test_complete_command_requires_matching_claim_when_provided(monkeypatch) -> None:
    cur = FakeCursor()
    conn = FakeConn(cur)
    repo = ControlRepository()
    monkeypatch.setattr(repo, "_connect", lambda: conn)

    updated = repo.complete_command(7, "applied", claim_token="worker-claim")

    query, params = cur.executed[0]
    assert updated is True
    assert "AND claim_token = %s" in query
    assert params == ("applied", None, 7, "worker-claim")
