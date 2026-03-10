from __future__ import annotations

import logging
from typing import Callable

from psycopg import Connection

from services.common.db import get_connection

logger = logging.getLogger(__name__)

AnalyticsStepCallback = Callable[[str, int], None]

def build_bi_documents(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_documents")
        cur.execute(
            """
            INSERT INTO bi_documents
                (
                    document_id,
                    scp_object_id,
                    canonical_number,
                    url,
                    title,
                    preview_text,
                    latest_snapshot_id,
                    latest_snapshot_at,
                    location_count
                )
            SELECT
                d.id AS document_id,
                d.scp_object_id,
                so.canonical_number,
                d.url,
                d.title,
                CASE
                    WHEN latest.clean_text IS NULL THEN NULL
                    ELSE SUBSTRING(latest.clean_text FROM 1 FOR 300)
                END AS preview_text,
                latest.id AS latest_snapshot_id,
                latest.created_at AS latest_snapshot_at,
                COALESCE(loc.location_count, 0) AS location_count
            FROM documents d
            LEFT JOIN scp_objects so ON so.id = d.scp_object_id
            LEFT JOIN LATERAL (
                SELECT ds.id, ds.created_at, ds.clean_text
                FROM document_snapshots ds
                WHERE ds.document_id = d.id
                ORDER BY ds.created_at DESC
                LIMIT 1
            ) latest ON true
            LEFT JOIN (
                SELECT document_id, COUNT(DISTINCT location_id) AS location_count
                FROM document_locations
                GROUP BY document_id
            ) loc ON loc.document_id = d.id
            """
        )
        return cur.rowcount


def build_bi_locations(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_locations")
        cur.execute(
            """
            INSERT INTO bi_locations
                (
                    location_id,
                    normalized_location,
                    country,
                    region,
                    city,
                    latitude,
                    longitude,
                    precision,
                    parent_location_id,
                    document_count
                )
            SELECT
                gl.id AS location_id,
                gl.normalized_location,
                gl.country,
                gl.region,
                gl.city,
                gl.latitude,
                gl.longitude,
                gl.precision,
                COALESCE(
                    (
                        SELECT p.id
                        FROM geo_locations p
                        WHERE
                            gl.city IS NOT NULL
                            AND gl.region IS NOT NULL
                            AND p.city IS NULL
                            AND p.region = gl.region
                            AND (
                                (p.country = gl.country)
                                OR (p.country IS NULL AND gl.country IS NULL)
                            )
                        ORDER BY p.normalized_location, p.id
                        LIMIT 1
                    ),
                    (
                        SELECT p.id
                        FROM geo_locations p
                        WHERE
                            (gl.city IS NOT NULL OR gl.region IS NOT NULL)
                            AND gl.country IS NOT NULL
                            AND p.city IS NULL
                            AND p.region IS NULL
                            AND p.country = gl.country
                        ORDER BY p.normalized_location, p.id
                        LIMIT 1
                    )
                ) AS parent_location_id,
                COALESCE(docs.document_count, 0) AS document_count
            FROM geo_locations gl
            LEFT JOIN (
                SELECT location_id, COUNT(DISTINCT document_id) AS document_count
                FROM document_locations
                GROUP BY location_id
            ) docs ON docs.location_id = gl.id
            """
        )
        return cur.rowcount


def build_bi_document_locations(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_document_locations")
        cur.execute(
            """
            INSERT INTO bi_document_locations
                (document_id, location_id, mention_count, evidence_quote)
            SELECT
                dl.document_id,
                dl.location_id,
                COUNT(*) AS mention_count,
                MIN(
                    CASE
                        WHEN lm.evidence_quote IS NULL OR lm.evidence_quote = '' THEN NULL
                        ELSE lm.evidence_quote
                    END
                ) AS evidence_quote
            FROM document_locations dl
            LEFT JOIN location_mentions lm ON lm.id = dl.mention_id
            GROUP BY dl.document_id, dl.location_id
            """
        )
        return cur.rowcount


def build_bi_location_hierarchy(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_location_hierarchy")
        cur.execute(
            """
            WITH RECURSIVE chain AS (
                SELECT
                    bl.location_id AS descendant_location_id,
                    bl.location_id AS ancestor_location_id,
                    0 AS depth
                FROM bi_locations bl

                UNION ALL

                SELECT
                    c.descendant_location_id,
                    parent.parent_location_id AS ancestor_location_id,
                    c.depth + 1 AS depth
                FROM chain c
                JOIN bi_locations parent ON parent.location_id = c.ancestor_location_id
                WHERE parent.parent_location_id IS NOT NULL
            ),
            dedup AS (
                SELECT
                    ancestor_location_id,
                    descendant_location_id,
                    MIN(depth) AS depth
                FROM chain
                GROUP BY ancestor_location_id, descendant_location_id
            )
            INSERT INTO bi_location_hierarchy
                (ancestor_location_id, descendant_location_id, depth)
            SELECT
                d.ancestor_location_id,
                d.descendant_location_id,
                d.depth
            FROM dedup d
            """
        )
        return cur.rowcount


def rebuild_analytics(*, on_step: AnalyticsStepCallback | None = None, start_index: int = 0) -> dict[str, int]:
    logger.info("analytics.rebuild_start")
    steps = [
        ("bi_documents", build_bi_documents),
        ("bi_locations", build_bi_locations),
        ("bi_document_locations", build_bi_document_locations),
        ("bi_location_hierarchy", build_bi_location_hierarchy),
    ]
    if start_index < 0:
        start_index = 0
    if start_index > len(steps):
        start_index = len(steps)

    documents_rows = 0
    locations_rows = 0
    links_rows = 0
    hierarchy_rows = 0
    with get_connection() as conn:
        for idx, (name, fn) in enumerate(steps):
            if idx < start_index:
                continue
            rows = fn(conn)
            if name == "bi_documents":
                documents_rows = rows
            elif name == "bi_locations":
                locations_rows = rows
            elif name == "bi_document_locations":
                links_rows = rows
            else:
                hierarchy_rows = rows
            if on_step:
                on_step(name, rows)
        conn.commit()

    stats = {
        "bi_documents": documents_rows,
        "bi_locations": locations_rows,
        "bi_document_locations": links_rows,
        "bi_location_hierarchy": hierarchy_rows,
    }
    logger.info("analytics.rebuild_done stats=%s", stats)
    return stats
