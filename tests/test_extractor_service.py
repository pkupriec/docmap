import pytest

from services.extractor import service


def test_extract_with_retries_succeeds_after_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_run_extraction(*, model: str, prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return "not-json"
        return '{"locations": []}'

    monkeypatch.setattr(service, "run_extraction", fake_run_extraction)
    monkeypatch.setattr(service.time, "sleep", lambda _: None)

    payload = service._extract_with_retries(model="gpt-oss:120b", prompt="x", max_retries=3)
    assert payload.locations == []
    assert calls["count"] == 2


def test_extract_with_retries_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "run_extraction", lambda **_: "not-json")
    monkeypatch.setattr(service.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError):
        service._extract_with_retries(model="gpt-oss:120b", prompt="x", max_retries=2)


def test_process_snapshot_replaces_existing_run_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def commit(self) -> None:
            return None

    calls: list[str] = []

    monkeypatch.setattr(service, "get_connection", lambda: DummyConn())
    monkeypatch.setattr(service, "get_snapshot_clean_text", lambda _conn, _snapshot_id: "clean text")
    monkeypatch.setattr(service, "build_extraction_prompt", lambda _text: "prompt")
    monkeypatch.setattr(service, "_extract_with_retries", lambda **kwargs: type("P", (), {"locations": []})())
    monkeypatch.setattr(service, "save_extraction_run", lambda _conn, **kwargs: "run-1")
    monkeypatch.setattr(service, "clear_mentions_and_links_for_run", lambda _conn, _run_id: calls.append("clear"))
    monkeypatch.setattr(service, "save_location_mentions", lambda _conn, **kwargs: 0)

    result = service.process_snapshot("snap-1")

    assert result.run_id == "run-1"
    assert calls == ["clear"]
