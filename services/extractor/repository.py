from __future__ import annotations

from psycopg import Connection

from services.extractor.models import ExtractionPayload


def get_snapshot_clean_text(conn: Connection, snapshot_id: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT clean_text FROM document_snapshots WHERE id = %s",
            (snapshot_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_unprocessed_snapshot_ids(conn: Connection, limit: int = 100) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ds.id
            FROM document_snapshots ds
            LEFT JOIN extraction_runs er ON er.snapshot_id = ds.id
            WHERE er.id IS NULL
            ORDER BY ds.created_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        return [str(row[0]) for row in cur.fetchall()]


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
            RETURNING id
            """,
            (snapshot_id, model, prompt_version, pipeline_version),
        )
        return str(cur.fetchone()[0])


def save_location_mentions(conn: Connection, *, run_id: str, payload: ExtractionPayload) -> int:
    if not payload.locations:
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
    return len(rows)
