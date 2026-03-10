import pytest

from services.crawler import service


def test_process_documents_isolates_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_process_document(url: str, **kwargs: object) -> service.CrawlResult:
        if "bad" in url:
            raise RuntimeError("boom")
        return service.CrawlResult(
            url=url,
            document_id="doc-1",
            snapshot_id=None,
            snapshot_created=False,
        )

    monkeypatch.setattr(service, "process_document", fake_process_document)

    result = service.process_documents(
        ["https://scp-wiki.wikidot.com/scp-173", "https://scp-wiki.wikidot.com/bad"],
    )

    assert result.processed == 2
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.failed_urls == ["https://scp-wiki.wikidot.com/bad"]


def test_filter_unprocessed_urls_delegates_to_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = [
        "https://scp-wiki.wikidot.com/scp-001",
        "https://scp-wiki.wikidot.com/scp-002",
    ]

    class _ConnCtx:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(service, "get_connection", lambda: _ConnCtx())
    monkeypatch.setattr(
        service,
        "filter_unprocessed_urls_in_db",
        lambda _conn, _urls, include_missing_pdf=True: [_urls[1]],
    )

    filtered = service.filter_unprocessed_urls(urls, include_missing_pdf=True)

    assert filtered == ["https://scp-wiki.wikidot.com/scp-002"]


def test_render_pdf_with_fallback_uses_text_renderer_after_primary_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "render_pdf_blob", lambda _url: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(service, "render_pdf_blob_from_text", lambda text, title=None: b"%PDF-fallback")

    result = service._render_pdf_with_fallback(
        "https://scp-wiki.wikidot.com/scp-173",
        "SCP-173",
        "Fallback text",
    )

    assert result == b"%PDF-fallback"
