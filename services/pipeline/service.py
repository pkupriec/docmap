from __future__ import annotations

import logging
from dataclasses import dataclass

from services.analytics import rebuild_analytics
from services.analytics.bigquery_exporter import export_all_bi_tables
from services.crawler import process_documents
from services.extractor import process_pending_snapshots
from services.geocoder import normalize_pending_mentions, process_pending_mentions


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    crawled_urls: int
    extracted_snapshots: int
    normalized_mentions: int
    geocoded_mentions: int


def run_incremental_pipeline(target_urls: list[str] | None = None) -> PipelineResult:
    crawled_urls = 0
    if target_urls:
        crawl_result = process_documents(target_urls)
        crawled_urls = crawl_result.succeeded
        logger.info(
            "pipeline.crawl_done processed=%s succeeded=%s failed=%s",
            crawl_result.processed,
            crawl_result.succeeded,
            crawl_result.failed,
        )

    extraction_results = process_pending_snapshots(limit=1000)
    normalized_count = normalize_pending_mentions(limit=5000)
    geocode_result = process_pending_mentions(limit=5000)
    rebuild_stats = rebuild_analytics()

    logger.info("pipeline.analytics_rebuilt stats=%s", rebuild_stats)
    export_all_bi_tables(mode="incremental")
    logger.info("pipeline.export_completed mode=incremental")

    return PipelineResult(
        crawled_urls=crawled_urls,
        extracted_snapshots=len(extraction_results),
        normalized_mentions=normalized_count,
        geocoded_mentions=geocode_result.linked,
    )


def run_single_document_pipeline(url: str) -> PipelineResult:
    return run_incremental_pipeline(target_urls=[url])


def run_full_pipeline(urls: list[str]) -> PipelineResult:
    return run_incremental_pipeline(target_urls=urls)
