from typing import Any

import pytest
import requests

from services.crawler.downloader import download_page


class _DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError("bad status")


def test_download_page_retries_and_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_get(*args: Any, **kwargs: Any) -> _DummyResponse:
        calls["count"] += 1
        if calls["count"] < 2:
            raise requests.ConnectionError("temporary")
        return _DummyResponse("<html>ok</html>")

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("time.sleep", lambda _: None)

    html = download_page("https://scp-wiki.wikidot.com/scp-173", max_retries=3)
    assert html == "<html>ok</html>"
    assert calls["count"] == 2


def test_download_page_fails_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*args: Any, **kwargs: Any) -> _DummyResponse:
        raise requests.ConnectionError("always fails")

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("time.sleep", lambda _: None)

    with pytest.raises(RuntimeError):
        download_page("https://scp-wiki.wikidot.com/scp-173", max_retries=3)
