from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from services.common.db import get_connection
from services.crawler.downloader import RequestThrottler, download_page
from services.crawler.parser import extract_clean_text, extract_title
from services.crawler.pdf_renderer import render_pdf_blob, render_pdf_blob_from_text
from services.crawler.repository import (
    canonical_number_from_url,
    filter_unprocessed_urls as filter_unprocessed_urls_in_db,
    get_latest_snapshot_missing_pdf,
    get_or_create_document,
    get_or_create_scp_object,
    set_snapshot_pdf_blob,
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


DocumentCallback = Callable[[int, int, int, str, CrawlResult | None, str | None], None]
StopCallback = Callable[[], bool]


def filter_unprocessed_urls(
    urls: list[str],
    *,
    include_missing_pdf: bool = True,
) -> list[str]:
    with get_connection() as conn:
        return filter_unprocessed_urls_in_db(conn, urls, include_missing_pdf=include_missing_pdf)


def _render_pdf_with_fallback(url: str, title: str | None, clean_text: str) -> bytes:
    try:
        return render_pdf_blob(url)
    except Exception as primary_exc:
        logger.warning("crawler.pdf_render_primary_failed url=%s error=%s", url, primary_exc)
    return render_pdf_blob_from_text(clean_text, title=title or url)


def process_document(
    url: str,
    *,
    resnapshot: bool = False,
    throttler: RequestThrottler | None = None,
) -> CrawlResult:
    logger.info("crawler.document_start url=%s resnapshot=%s", url, resnapshot)
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

        snapshot_id, created = save_snapshot_if_changed(
            conn,
            document_id=document_id,
            raw_html=raw_html,
            clean_text=clean_text,
            pdf_blob=None,
            resnapshot=resnapshot,
        )

        if created:
            try:
                pdf_blob = _render_pdf_with_fallback(url, title, clean_text)
                if snapshot_id:
                    set_snapshot_pdf_blob(conn, snapshot_id, pdf_blob)
            except Exception as exc:
                logger.warning(
                    "crawler.pdf_render_failed_nonfatal url=%s error=%s",
                    url,
                    exc,
                )
            conn.commit()
            logger.info("crawler.snapshot_created url=%s snapshot_id=%s", url, snapshot_id)
        else:
            missing_pdf_snapshot_id = get_latest_snapshot_missing_pdf(conn, document_id)
            if missing_pdf_snapshot_id:
                try:
                    pdf_blob = _render_pdf_with_fallback(url, title, clean_text)
                    set_snapshot_pdf_blob(conn, missing_pdf_snapshot_id, pdf_blob)
                    logger.info(
                        "crawler.snapshot_pdf_backfilled url=%s snapshot_id=%s",
                        url,
                        missing_pdf_snapshot_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "crawler.pdf_backfill_failed_nonfatal url=%s snapshot_id=%s error=%s",
                        url,
                        missing_pdf_snapshot_id,
                        exc,
                    )
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
    resnapshot: bool = False,
    on_document: DocumentCallback | None = None,
    should_stop: StopCallback | None = None,
) -> BatchCrawlResult:
    logger.info("crawler.batch_start urls=%s resnapshot=%s", len(urls), resnapshot)
    throttler = RequestThrottler()
    results: list[CrawlResult] = []
    failed_urls: list[str] = []

    for idx, url in enumerate(urls, start=1):
        if should_stop and should_stop():
            logger.info("crawler.batch_stop_requested processed=%s total=%s", idx - 1, len(urls))
            break
        try:
            result = process_document(
                url,
                resnapshot=resnapshot,
                throttler=throttler,
            )
            results.append(result)
            if on_document:
                on_document(idx, len(results), len(failed_urls), url, result, None)
        except Exception:
            logger.exception("crawler.process_failed url=%s", url)
            failed_urls.append(url)
            if on_document:
                on_document(idx, len(results), len(failed_urls), url, None, "process_failed")

    result = BatchCrawlResult(
        processed=len(urls),
        succeeded=len(results),
        failed=len(failed_urls),
        results=results,
        failed_urls=failed_urls,
    )
    logger.info(
        "crawler.batch_done processed=%s succeeded=%s failed=%s",
        result.processed,
        result.succeeded,
        result.failed,
    )
    return result
