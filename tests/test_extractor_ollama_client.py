import pytest

from services.extractor import ollama_client


def test_timeout_defaults_to_300_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_TIMEOUT_SECONDS", raising=False)
    assert ollama_client._get_ollama_timeout_seconds() == 300


def test_timeout_falls_back_to_default_when_env_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "abc")
    assert ollama_client._get_ollama_timeout_seconds() == 300


def test_run_extraction_uses_env_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"response": "ok"}

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "480")
    monkeypatch.setattr(ollama_client.requests, "post", fake_post)

    response = ollama_client.run_extraction(model="test-model", prompt="test-prompt")
    assert response == "ok"
    assert captured["url"] == "http://host.docker.internal:11434/api/generate"
    assert captured["timeout"] == 480
