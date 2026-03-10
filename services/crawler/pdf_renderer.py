from __future__ import annotations

import shutil
import subprocess
import logging
import tempfile
import html
from pathlib import Path

logger = logging.getLogger(__name__)


def render_pdf_blob(url: str, *, timeout_seconds: int = 90) -> bytes:
    if shutil.which("wkhtmltopdf") is None:
        logger.error("crawler.pdf_renderer_missing_binary")
        raise RuntimeError("wkhtmltopdf is not installed or not in PATH")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        logger.info("crawler.pdf_render_start url=%s", url)
        command = [
            "wkhtmltopdf",
            "--quiet",
            "--load-error-handling",
            "ignore",
            "--load-media-error-handling",
            "ignore",
            url,
            str(tmp_path),
        ]
        try:
            _run_wkhtmltopdf(command, timeout_seconds=timeout_seconds)
        except RuntimeError as exc:
            if "ContentNotFoundError" not in str(exc):
                raise
            logger.warning("crawler.pdf_render_retry url=%s reason=ContentNotFoundError", url)
            _run_wkhtmltopdf(command, timeout_seconds=timeout_seconds)
        blob = tmp_path.read_bytes()
        logger.info("crawler.pdf_render_success url=%s bytes=%s", url, len(blob))
        return blob
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            logger.warning("crawler.pdf_renderer_tempfile_cleanup_failed path=%s", tmp_path)


def render_pdf_blob_from_text(
    text: str,
    *,
    title: str | None = None,
    timeout_seconds: int = 90,
) -> bytes:
    if shutil.which("wkhtmltopdf") is None:
        logger.error("crawler.pdf_renderer_missing_binary")
        raise RuntimeError("wkhtmltopdf is not installed or not in PATH")

    safe_title = html.escape(title or "DocMap Snapshot")
    safe_text = html.escape(text or "")
    html_payload = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{safe_title}</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.4;}pre{white-space:pre-wrap;word-break:break-word;}</style>"
        "</head><body>"
        f"<h1>{safe_title}</h1><pre>{safe_text}</pre>"
        "</body></html>"
    )

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as src:
        src.write(html_payload)
        src_path = Path(src.name)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as out:
        out_path = Path(out.name)

    try:
        logger.info("crawler.pdf_render_fallback_start title=%s chars=%s", title or "", len(text or ""))
        _run_wkhtmltopdf(
            [
                "wkhtmltopdf",
                "--quiet",
                "--disable-javascript",
                str(src_path),
                str(out_path),
            ],
            timeout_seconds=timeout_seconds,
        )
        blob = out_path.read_bytes()
        logger.info("crawler.pdf_render_fallback_success bytes=%s", len(blob))
        return blob
    finally:
        try:
            src_path.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)
        except Exception:
            logger.warning("crawler.pdf_renderer_tempfile_cleanup_failed path=%s", out_path)


def _run_wkhtmltopdf(command: list[str], *, timeout_seconds: int) -> None:
    result = subprocess.run(
        command,
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    message = stderr or stdout or f"wkhtmltopdf exited with code {result.returncode}"
    raise RuntimeError(message)
