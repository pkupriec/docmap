from __future__ import annotations

from psycopg import Connection

from services.common.db import get_connection
from services.geocoder.normalization import normalize_location_name


def normalize_pending_mentions(limit: int = 1000) -> int:
    with get_connection() as conn:
        return _normalize_pending_mentions(conn, limit=limit)


def _normalize_pending_mentions(conn: Connection, *, limit: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, normalized_location, precision
            FROM location_mentions
            WHERE normalized_location IS NOT NULL
            ORDER BY id
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    updates: list[tuple[str, str]] = []
    for mention_id, normalized_location, precision in rows:
        old_value = normalized_location or ""
        new_value = normalize_location_name(old_value, precision or "unknown")
        if new_value and new_value != old_value:
            updates.append((new_value, str(mention_id)))

    if not updates:
        return 0

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
    return len(updates)
