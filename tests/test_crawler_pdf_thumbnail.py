from __future__ import annotations

from io import BytesIO

import pypdfium2 as pdfium

from services.crawler.pdf_thumbnail import render_pdf_thumbnail


def test_render_pdf_thumbnail_produces_small_webp() -> None:
    document = pdfium.PdfDocument.new()
    document.new_page(612, 792)
    buffer = BytesIO()
    document.save(buffer)
    document.close()
    pdf = buffer.getvalue()

    thumbnail = render_pdf_thumbnail(pdf, max_width=240)

    assert thumbnail.startswith(b"RIFF")
    assert thumbnail[8:12] == b"WEBP"
    assert len(thumbnail) < len(pdf)
