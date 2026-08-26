from __future__ import annotations

from io import BytesIO

import pypdfium2 as pdfium


def render_pdf_thumbnail(pdf_blob: bytes, *, max_width: int = 320, quality: int = 76) -> bytes:
    """Render the first PDF page once; list views serve this compact WebP."""
    document = pdfium.PdfDocument(pdf_blob)
    try:
        if len(document) == 0:
            raise ValueError("PDF has no pages")
        page = document[0]
        try:
            width = max(float(page.get_width()), 1.0)
            scale = max(1.0, min(3.0, max_width / width))
            image = page.render(scale=scale).to_pil()
            if image.width > max_width:
                height = max(1, round(image.height * max_width / image.width))
                image = image.resize((max_width, height))
            output = BytesIO()
            image.save(output, format="WEBP", quality=quality, method=4)
            return output.getvalue()
        finally:
            page.close()
    finally:
        document.close()
