from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from services.analytics import rebuild_analytics
from services.analytics.bigquery_exporter import export_all_bi_tables
from services.crawler import generate_scp_urls, process_documents
from services.extractor import process_pending_snapshots
from services.geocoder import normalize_pending_mentions, process_pending_mentions


logger = logging.getLogger(__name__)
SCP_START = 1
SCP_END = 20


@dataclass(frozen=True)
class StageSummary:
    run_id: str
    stage: str
    processed: int
    succeeded: int
    failed: int
    skipped: int
    duration_seconds: float


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    crawled_urls: int
    extracted_snapshots: int
    normalized_mentions: int
    geocoded_mentions: int


def run_incremental_pipeline(target_urls: list[str] | None = None) -> PipelineResult:
    run_id = str(uuid.uuid4())
    started_at = time.monotonic()
    urls = target_urls if target_urls is not None else generate_scp_urls(SCP_START, SCP_END)
    logger.info("pipeline.run_start run_id=%s mode=incremental urls=%s", run_id, len(urls))

    stage_started = time.monotonic()
    crawl_result = process_documents(urls)
    _log_stage_summary(
        StageSummary(
            run_id=run_id,
            stage="crawl",
            processed=crawl_result.processed,
            succeeded=crawl_result.succeeded,
            failed=crawl_result.failed,
            skipped=0,
            duration_seconds=round(time.monotonic() - stage_started, 2),
        )
    )

    stage_started = time.monotonic()
    extraction_results = process_pending_snapshots(limit=1000)
    _log_stage_summary(
        StageSummary(
            run_id=run_id,
            stage="extract",
            processed=len(extraction_results),
            succeeded=len(extraction_results),
            failed=0,
            skipped=0,
            duration_seconds=round(time.monotonic() - stage_started, 2),
        )
    )

    stage_started = time.monotonic()
    normalized_count = normalize_pending_mentions(limit=5000)
    _log_stage_summary(
        StageSummary(
            run_id=run_id,
            stage="normalize",
            processed=normalized_count,
            succeeded=normalized_count,
            failed=0,
            skipped=0,
            duration_seconds=round(time.monotonic() - stage_started, 2),
        )
    )

    stage_started = time.monotonic()
    geocode_result = process_pending_mentions(limit=5000)
    _log_stage_summary(
        StageSummary(
            run_id=run_id,
            stage="geocode",
            processed=geocode_result.processed,
            succeeded=geocode_result.linked,
            failed=0,
            skipped=geocode_result.unresolved,
            duration_seconds=round(time.monotonic() - stage_started, 2),
        )
    )

    stage_started = time.monotonic()
    rebuild_stats = rebuild_analytics()
    _log_stage_summary(
        StageSummary(
            run_id=run_id,
            stage="analytics",
            processed=sum(rebuild_stats.values()),
            succeeded=sum(rebuild_stats.values()),
            failed=0,
            skipped=0,
            duration_seconds=round(time.monotonic() - stage_started, 2),
        )
    )

    stage_started = time.monotonic()
    export_all_bi_tables(mode="incremental")
    _log_stage_summary(
        StageSummary(
            run_id=run_id,
            stage="export",
            processed=3,
            succeeded=3,
            failed=0,
            skipped=0,
            duration_seconds=round(time.monotonic() - stage_started, 2),
        )
    )

    result = PipelineResult(
        run_id=run_id,
        crawled_urls=crawl_result.succeeded,
        extracted_snapshots=len(extraction_results),
        normalized_mentions=normalized_count,
        geocoded_mentions=geocode_result.linked,
    )
    duration = round(time.monotonic() - started_at, 2)
    _log_stage_summary(
        StageSummary(
            run_id=run_id,
            stage="pipeline",
            processed=result.crawled_urls,
            succeeded=result.crawled_urls,
            failed=0,
            skipped=0,
            duration_seconds=duration,
        )
    )
    logger.info("pipeline.run_done run_id=%s result=%s", run_id, result)
    return result


def run_single_document_pipeline(url: str) -> PipelineResult:
    return run_incremental_pipeline(target_urls=[url])


def run_full_pipeline() -> PipelineResult:
    logger.info("pipeline.full_mode_start range_start=%s range_end=%s", SCP_START, SCP_END)
    return run_incremental_pipeline(target_urls=generate_scp_urls(SCP_START, SCP_END))


def _log_stage_summary(summary: StageSummary) -> None:
    logger.info(
        "pipeline.stage_summary run_id=%s stage=%s processed=%s succeeded=%s failed=%s skipped=%s duration_seconds=%s",
        summary.run_id,
        summary.stage,
        summary.processed,
        summary.succeeded,
        summary.failed,
        summary.skipped,
        summary.duration_seconds,
    )
