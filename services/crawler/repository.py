from __future__ import annotations

import re
import logging
from dataclasses import dataclass

from psycopg import Connection

from services.crawler.snapshot import should_create_snapshot

SCP_URL_PATTERN = re.compile(r"/scp-(\d+)$")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LatestSnapshot:
    snapshot_id: str
    clean_text: str


def canonical_number_from_url(url: str) -> str | None:
    match = SCP_URL_PATTERN.search(url.rstrip("/"))
    if not match:
        return None
    number = int(match.group(1))
    suffix = f"{number:03d}" if number < 1000 else str(number)
    return f"SCP-{suffix}"


def get_or_create_scp_object(conn: Connection, canonical_number: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scp_objects (canonical_number)
            VALUES (%s)
            ON CONFLICT (canonical_number) DO UPDATE
            SET canonical_number = EXCLUDED.canonical_number
            RETURNING id
            """,
            (canonical_number,),
        )
        return str(cur.fetchone()[0])


def get_or_create_document(
    conn: Connection,
    *,
    url: str,
    scp_object_id: str | None,
    title: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (scp_object_id, url, title, last_checked_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (url) DO UPDATE
            SET title = COALESCE(EXCLUDED.title, documents.title),
                scp_object_id = COALESCE(documents.scp_object_id, EXCLUDED.scp_object_id),
                last_checked_at = now()
            RETURNING id
            """,
            (scp_object_id, url, title),
        )
        return str(cur.fetchone()[0])


def get_latest_snapshot(conn: Connection, document_id: str) -> LatestSnapshot | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, clean_text
            FROM document_snapshots
            WHERE document_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (document_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return LatestSnapshot(snapshot_id=str(row[0]), clean_text=row[1] or "")


def save_snapshot_if_changed(
    conn: Connection,
    *,
    document_id: str,
    raw_html: str,
    clean_text: str,
    pdf_blob: bytes | None,
    resnapshot: bool = False,
) -> tuple[str | None, bool]:
    latest = get_latest_snapshot(conn, document_id)
    previous_text = latest.clean_text if latest else None
    create = should_create_snapshot(clean_text, previous_text, resnapshot=resnapshot)
    if not create:
        logger.info("crawler.snapshot_unchanged document_id=%s", document_id)
        return (None, False)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_snapshots (document_id, raw_html, clean_text, pdf_blob)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (document_id, raw_html, clean_text, pdf_blob),
        )
        snapshot_id = str(cur.fetchone()[0])
        logger.info("crawler.snapshot_saved document_id=%s snapshot_id=%s", document_id, snapshot_id)
        return (snapshot_id, True)


def set_snapshot_pdf_blob(conn: Connection, snapshot_id: str, pdf_blob: bytes) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE document_snapshots
            SET pdf_blob = %s
            WHERE id = %s
            """,
            (pdf_blob, snapshot_id),
        )
