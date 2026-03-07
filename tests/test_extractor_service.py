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
