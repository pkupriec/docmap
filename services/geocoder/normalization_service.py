from __future__ import annotations

import logging
from typing import Callable
from psycopg import Connection

from services.common.db import get_connection
from services.geocoder.normalization import normalize_location_name

logger = logging.getLogger(__name__)

NormalizeCallback = Callable[[int, int, int], None]

def normalize_pending_mentions(
    limit: int = 1000,
    *,
    invalid_threshold: int = 5,
    on_progress: NormalizeCallback | None = None,
) -> int:
    logger.info("geocoder.normalize_batch_start limit=%s", limit)
    with get_connection() as conn:
        updated = _normalize_pending_mentions(
            conn,
            batch_size=min(max(limit, 1), 1000),
            max_items=limit,
            invalid_threshold=invalid_threshold,
            on_progress=on_progress,
        )
    logger.info("geocoder.normalize_batch_done updated=%s", updated)
    return updated


def _normalize_pending_mentions(
    conn: Connection,
    *,
    batch_size: int,
    max_items: int | None,
    invalid_threshold: int,
    on_progress: NormalizeCallback | None = None,
) -> int:
    updated_count = 0
    invalid_count = 0
    offset = 0
    scanned_total = 0

    while True:
        if max_items is not None and scanned_total >= max_items:
            break
        fetch_limit = batch_size
        if max_items is not None:
            remaining = max_items - scanned_total
            if remaining <= 0:
                break
            fetch_limit = min(fetch_limit, remaining)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, normalized_location, precision
                FROM location_mentions
                WHERE normalized_location IS NOT NULL
                  AND btrim(normalized_location) <> ''
                ORDER BY id
                LIMIT %s OFFSET %s
                """,
                (fetch_limit, offset),
            )
            rows = cur.fetchall()
        if not rows:
            break

        logger.info("geocoder.normalize_candidates_loaded count=%s offset=%s", len(rows), offset)
        scanned_total += len(rows)
        offset += len(rows)

        updates: list[tuple[str, str]] = []
        for mention_id, normalized_location, precision in rows:
            old_value = normalized_location or ""
            new_value = normalize_location_name(old_value, precision or "unknown").strip()
            if not new_value:
                invalid_count += 1
                logger.warning(
                    "geocoder.normalize_invalid mention_id=%s old_value=%s invalid_count=%s",
                    mention_id,
                    old_value,
                    invalid_count,
                )
                if invalid_count >= invalid_threshold:
                    raise RuntimeError(
                        f"Normalization produced too many invalid values: {invalid_count}"
                    )
                continue
            if new_value != old_value:
                updates.append((new_value, str(mention_id)))

        if not updates:
            if on_progress:
                on_progress(scanned_total, updated_count, invalid_count)
            continue

        with conn.cursor() as cur:
            cur.executemany(
                """
                UPDATE location_mentions
                SET normalized_location = %s
                WHERE id = %s
                """,
                updates,
            )
        conn.commit()
        updated_count += len(updates)
        logger.info("geocoder.normalize_applied updates=%s total_updates=%s", len(updates), updated_count)
        if on_progress:
            on_progress(scanned_total, updated_count, invalid_count)

    if scanned_total == 0:
        logger.info("geocoder.normalize_no_changes")
        if on_progress:
            on_progress(0, updated_count, invalid_count)
    return updated_count
