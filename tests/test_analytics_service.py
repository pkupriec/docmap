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

    stats = service.rebuild_analytics()

    assert stats == {
        "bi_documents": 10,
        "bi_locations": 5,
        "bi_document_locations": 12,
        "bi_location_hierarchy": 7,
    }
    assert conn.committed is True
