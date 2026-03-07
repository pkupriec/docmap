from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def render_pdf(url: str, output_path: str, *, timeout_seconds: int = 90) -> str:
    if shutil.which("wkhtmltopdf") is None:
        raise RuntimeError("wkhtmltopdf is not installed or not in PATH")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["wkhtmltopdf", "--quiet", url, str(output)],
        check=True,
        timeout=timeout_seconds,
    )
    return str(output)
