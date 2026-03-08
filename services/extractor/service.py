from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Callable

from services.common.db import get_connection
from services.extractor.ollama_client import run_extraction
from services.extractor.prompt_builder import build_extraction_prompt
from services.extractor.repository import (
    get_snapshot_clean_text,
    get_unprocessed_snapshot_ids,
    save_extraction_run,
    save_location_mentions,
)
from services.extractor.validator import parse_extraction_json, validate_extraction_response


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractionResult:
    snapshot_id: str
    run_id: str
    mentions_count: int


SnapshotCallback = Callable[[int, int, int, str, ExtractionResult | None, str | None], None]


def process_snapshot(
    snapshot_id: str,
    *,
    model: str = "gpt-oss:120b",
    prompt_version: str = "v1",
    pipeline_version: str = "v1",
    max_retries: int = 3,
) -> ExtractionResult:
    logger.info("extractor.snapshot_start snapshot_id=%s model=%s", snapshot_id, model)
    with get_connection() as conn:
        clean_text = get_snapshot_clean_text(conn, snapshot_id)
        if not clean_text:
            raise ValueError(f"Snapshot not found or empty: {snapshot_id}")

        prompt = build_extraction_prompt(clean_text)
        payload = _extract_with_retries(
            model=model,
            prompt=prompt,
            max_retries=max_retries,
        )

        run_id = save_extraction_run(
            conn,
            snapshot_id=snapshot_id,
            model=model,
            prompt_version=prompt_version,
            pipeline_version=pipeline_version,
        )
        mentions_count = save_location_mentions(conn, run_id=run_id, payload=payload)
        conn.commit()

    logger.info(
        "extractor.snapshot_processed snapshot_id=%s run_id=%s mentions=%s",
        snapshot_id,
        run_id,
        mentions_count,
    )
    return ExtractionResult(snapshot_id=snapshot_id, run_id=run_id, mentions_count=mentions_count)


def process_pending_snapshots(
    *,
    limit: int = 100,
    model: str = "gpt-oss:120b",
    prompt_version: str = "v1",
    pipeline_version: str = "v1",
    max_retries: int = 3,
    on_snapshot: SnapshotCallback | None = None,
) -> list[ExtractionResult]:
    with get_connection() as conn:
        snapshot_ids = get_unprocessed_snapshot_ids(conn, limit=limit)

    logger.info("extractor.batch_start snapshots=%s limit=%s", len(snapshot_ids), limit)
    results: list[ExtractionResult] = []
    failed = 0
    total = len(snapshot_ids)
    for idx, snapshot_id in enumerate(snapshot_ids, start=1):
        try:
            result = process_snapshot(
                snapshot_id,
                model=model,
                prompt_version=prompt_version,
                pipeline_version=pipeline_version,
                max_retries=max_retries,
            )
            results.append(result)
            if on_snapshot:
                on_snapshot(idx, total, len(results), snapshot_id, result, None)
        except Exception:
            failed += 1
            logger.exception("extractor.snapshot_failed snapshot_id=%s", snapshot_id)
            if on_snapshot:
                on_snapshot(idx, total, len(results), snapshot_id, None, "snapshot_failed")
    logger.info("extractor.batch_done succeeded=%s failed=%s", len(results), failed)
    return results


def _extract_with_retries(*, model: str, prompt: str, max_retries: int):
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            raw_response = run_extraction(model=model, prompt=prompt)
            parsed = parse_extraction_json(raw_response)
            return validate_extraction_response(parsed)
        except (json.JSONDecodeError, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt == max_retries:
                break
            backoff_seconds = 2 ** (attempt - 1)
            logger.warning("extractor.retry attempt=%s reason=%s", attempt, type(exc).__name__)
            time.sleep(backoff_seconds)
    logger.error("extractor.retries_exhausted model=%s max_retries=%s", model, max_retries)
    raise RuntimeError("Extraction failed after retries") from last_error
