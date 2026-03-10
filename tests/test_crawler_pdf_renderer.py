from __future__ import annotations

from pathlib import Path

import pytest

from services.crawler import pdf_renderer


def test_render_pdf_blob_retries_on_content_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class _Result:
        def __init__(self, returncode: int, stderr: str = "", stdout: str = "") -> None:
            self.returncode = returncode
            self.stderr = stderr
            self.stdout = stdout

    def _fake_run(command, **kwargs):
        calls.append(command)
        output_path = Path(command[-1])
        if len(calls) == 1:
            return _Result(returncode=1, stderr="Exit with code 1 due to network error: ContentNotFoundError")
        output_path.write_bytes(b"%PDF-1.4 test")
        return _Result(returncode=0)

    monkeypatch.setattr(pdf_renderer.shutil, "which", lambda _: "/usr/bin/wkhtmltopdf")
    monkeypatch.setattr(pdf_renderer.subprocess, "run", _fake_run)

    blob = pdf_renderer.render_pdf_blob("https://scp-wiki.wikidot.com/scp-173")

    assert blob.startswith(b"%PDF-1.4")
    assert len(calls) == 2


def test_render_pdf_blob_raises_runtime_error_with_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Result:
        returncode = 1
        stderr = "network error"
        stdout = ""

    monkeypatch.setattr(pdf_renderer.shutil, "which", lambda _: "/usr/bin/wkhtmltopdf")
    monkeypatch.setattr(pdf_renderer.subprocess, "run", lambda *args, **kwargs: _Result())

    with pytest.raises(RuntimeError, match="network error"):
        pdf_renderer.render_pdf_blob("https://scp-wiki.wikidot.com/scp-9999")
