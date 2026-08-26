from __future__ import annotations

import argparse
import logging

from services.common.db import get_connection
from services.crawler.pdf_thumbnail import render_pdf_thumbnail


logger = logging.getLogger(__name__)


def backfill_latest_pdf_thumbnails(*, limit: int | None = None, batch_size: int = 25) -> dict[str, int]:
    processed = 0
    updated = 0
    failed = 0
    last_id: str | None = None

    with get_connection() as conn:
        while limit is None or processed < limit:
            page_size = batch_size if limit is None else min(batch_size, limit - processed)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH latest AS (
                        SELECT DISTINCT ON (document_id) id, document_id, pdf_blob, pdf_thumbnail_webp
                        FROM document_snapshots
                        ORDER BY document_id, created_at DESC, id DESC
                    )
                    SELECT id::text, pdf_blob
                    FROM latest
                    WHERE pdf_blob IS NOT NULL
                      AND pdf_thumbnail_webp IS NULL
                      AND (%s::uuid IS NULL OR id > %s::uuid)
                    ORDER BY id
                    LIMIT %s
                    """,
                    (last_id, last_id, page_size),
                )
                rows = cur.fetchall()
            if not rows:
                break

            updates: list[tuple[bytes, str]] = []
            for snapshot_id, pdf_blob in rows:
                processed += 1
                last_id = str(snapshot_id)
                try:
                    updates.append((render_pdf_thumbnail(bytes(pdf_blob)), last_id))
                except Exception:
                    failed += 1
                    logger.exception("crawler.thumbnail_backfill_failed snapshot_id=%s", snapshot_id)

            if updates:
                with conn.cursor() as cur:
                    cur.executemany(
                        "UPDATE document_snapshots SET pdf_thumbnail_webp = %s WHERE id = %s::uuid",
                        updates,
                    )
                updated += len(updates)
            conn.commit()
            logger.info(
                "crawler.thumbnail_backfill_progress processed=%s updated=%s failed=%s",
                processed,
                updated,
                failed,
            )

    return {"processed": processed, "updated": updated, "failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate WebP previews for latest stored PDFs")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()
    print(backfill_latest_pdf_thumbnails(limit=args.limit, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
