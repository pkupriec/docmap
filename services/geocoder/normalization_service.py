from __future__ import annotations

import logging
from psycopg import Connection

from services.common.db import get_connection
from services.geocoder.normalization import normalize_location_name

logger = logging.getLogger(__name__)

def normalize_pending_mentions(
    limit: int = 1000,
    *,
    invalid_threshold: int = 5,
) -> int:
    logger.info("geocoder.normalize_batch_start batch_size=%s", limit)
    with get_connection() as conn:
        updated = _normalize_pending_mentions(
            conn,
            batch_size=limit,
            invalid_threshold=invalid_threshold,
        )
    logger.info("geocoder.normalize_batch_done updated=%s", updated)
    return updated


def _normalize_pending_mentions(
    conn: Connection,
    *,
    batch_size: int,
    invalid_threshold: int,
) -> int:
    updated_count = 0
    invalid_count = 0
    offset = 0

    while True:
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
                (batch_size, offset),
            )
            rows = cur.fetchall()
        if not rows:
            break

        logger.info("geocoder.normalize_candidates_loaded count=%s offset=%s", len(rows), offset)
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

    if updated_count == 0:
        logger.info("geocoder.normalize_no_changes")
    return updated_count
