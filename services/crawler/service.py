from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from services.common.db import get_connection
from services.crawler.downloader import RequestThrottler, download_page
from services.crawler.parser import extract_clean_text, extract_title
from services.crawler.pdf_renderer import render_pdf
from services.crawler.repository import (
    canonical_number_from_url,
    get_or_create_document,
    get_or_create_scp_object,
    save_snapshot_if_changed,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CrawlResult:
    url: str
    document_id: str
    snapshot_id: str | None
    snapshot_created: bool


@dataclass(frozen=True)
class BatchCrawlResult:
    processed: int
    succeeded: int
    failed: int
    results: list[CrawlResult]
    failed_urls: list[str]


def process_document(
    url: str,
    *,
    pdf_dir: str = "snapshots",
    resnapshot: bool = False,
    throttler: RequestThrottler | None = None,
) -> CrawlResult:
    raw_html = download_page(url, throttler=throttler)
    clean_text = extract_clean_text(raw_html)
    title = extract_title(raw_html)

    if len(clean_text) < 2000:
        logger.warning(
            "crawler.clean_text_short url=%s length=%s",
            url,
            len(clean_text),
        )

    canonical_number = canonical_number_from_url(url)
    with get_connection() as conn:
        scp_object_id: str | None = None
        if canonical_number:
            scp_object_id = get_or_create_scp_object(conn, canonical_number)

        document_id = get_or_create_document(
            conn,
            url=url,
            scp_object_id=scp_object_id,
            title=title,
        )

        pdf_path = _build_pdf_path(url, pdf_dir)
        snapshot_id, created = save_snapshot_if_changed(
            conn,
            document_id=document_id,
            raw_html=raw_html,
            clean_text=clean_text,
            pdf_path=pdf_path,
            resnapshot=resnapshot,
        )

        if created:
            render_pdf(url, pdf_path)
            conn.commit()
            logger.info("crawler.snapshot_created url=%s snapshot_id=%s", url, snapshot_id)
        else:
            conn.commit()
            logger.info("crawler.snapshot_skipped_unchanged url=%s", url)

    return CrawlResult(
        url=url,
        document_id=document_id,
        snapshot_id=snapshot_id,
        snapshot_created=created,
    )


def process_documents(
    urls: list[str],
    *,
    pdf_dir: str = "snapshots",
    resnapshot: bool = False,
) -> BatchCrawlResult:
    throttler = RequestThrottler()
    results: list[CrawlResult] = []
    failed_urls: list[str] = []

    for url in urls:
        try:
            result = process_document(
                url,
                pdf_dir=pdf_dir,
                resnapshot=resnapshot,
                throttler=throttler,
            )
            results.append(result)
        except Exception:
            logger.exception("crawler.process_failed url=%s", url)
            failed_urls.append(url)

    return BatchCrawlResult(
        processed=len(urls),
        succeeded=len(results),
        failed=len(failed_urls),
        results=results,
        failed_urls=failed_urls,
    )


def _build_pdf_path(url: str, pdf_dir: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    path = Path(pdf_dir) / f"{slug}_{timestamp}.pdf"
    return str(path)
