from __future__ import annotations

import shutil
import subprocess
import logging
import tempfile
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
        subprocess.run(
            ["wkhtmltopdf", "--quiet", url, str(tmp_path)],
            check=True,
            timeout=timeout_seconds,
        )
        blob = tmp_path.read_bytes()
        logger.info("crawler.pdf_render_success url=%s bytes=%s", url, len(blob))
        return blob
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            logger.warning("crawler.pdf_renderer_tempfile_cleanup_failed path=%s", tmp_path)
