from __future__ import annotations

import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def render_pdf(url: str, output_path: str, *, timeout_seconds: int = 90) -> str:
    if shutil.which("wkhtmltopdf") is None:
        logger.error("crawler.pdf_renderer_missing_binary")
        raise RuntimeError("wkhtmltopdf is not installed or not in PATH")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    logger.info("crawler.pdf_render_start url=%s output_path=%s", url, output_path)

    subprocess.run(
        ["wkhtmltopdf", "--quiet", url, str(output)],
        check=True,
        timeout=timeout_seconds,
    )
    logger.info("crawler.pdf_render_success url=%s output_path=%s", url, output_path)
    return str(output)
