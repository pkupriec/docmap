from __future__ import annotations

import logging

from psycopg import Connection

from services.extractor.models import ExtractionPayload

logger = logging.getLogger(__name__)

def get_snapshot_clean_text(conn: Connection, snapshot_id: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT clean_text FROM document_snapshots WHERE id = %s",
            (snapshot_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_unprocessed_snapshot_ids(conn: Connection, limit: int = 100, offset: int = 0) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ds.id
            FROM document_snapshots ds
            LEFT JOIN extraction_runs er ON er.snapshot_id = ds.id
            WHERE er.id IS NULL
            ORDER BY ds.created_at ASC, ds.id ASC
            LIMIT %s
            OFFSET %s
            """,
            (limit, offset),
        )
        snapshot_ids = [str(row[0]) for row in cur.fetchall()]
    logger.info("extractor.pending_snapshots_loaded count=%s limit=%s offset=%s", len(snapshot_ids), limit, offset)
    return snapshot_ids


def get_all_snapshot_ids(conn: Connection, limit: int = 100, offset: int = 0) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ds.id
            FROM document_snapshots ds
            ORDER BY ds.created_at ASC, ds.id ASC
            LIMIT %s
            OFFSET %s
            """,
            (limit, offset),
        )
        snapshot_ids = [str(row[0]) for row in cur.fetchall()]
    logger.info("extractor.all_snapshots_loaded count=%s limit=%s offset=%s", len(snapshot_ids), limit, offset)
    return snapshot_ids


def save_extraction_run(
    conn: Connection,
    *,
    snapshot_id: str,
    model: str,
    prompt_version: str,
    pipeline_version: str,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO extraction_runs (snapshot_id, model, prompt_version, pipeline_version)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (snapshot_id) DO UPDATE
            SET
                model = EXCLUDED.model,
                prompt_version = EXCLUDED.prompt_version,
                pipeline_version = EXCLUDED.pipeline_version,
                created_at = NOW()
            RETURNING id
            """,
            (snapshot_id, model, prompt_version, pipeline_version),
        )
        return str(cur.fetchone()[0])


def clear_mentions_and_links_for_run(conn: Connection, run_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM document_locations dl
            USING location_mentions lm
            WHERE dl.mention_id = lm.id
              AND lm.run_id = %s
            """,
            (run_id,),
        )
        cur.execute(
            """
            DELETE FROM location_mentions
            WHERE run_id = %s
            """,
            (run_id,),
        )


def save_location_mentions(conn: Connection, *, run_id: str, payload: ExtractionPayload) -> int:
    if not payload.locations:
        logger.info("extractor.mentions_empty run_id=%s", run_id)
        return 0

    rows = [
        (
            run_id,
            item.mention_text,
            item.normalized_location,
            item.precision,
            item.relation_type,
            item.confidence,
            item.evidence_quote,
        )
        for item in payload.locations
    ]

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO location_mentions
            (run_id, mention_text, normalized_location, precision, relation_type, confidence, evidence_quote)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
    logger.info("extractor.mentions_saved run_id=%s count=%s", run_id, len(rows))
    return len(rows)
