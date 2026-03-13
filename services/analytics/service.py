from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

from psycopg import Connection

from services.common.db import get_connection
from services.analytics.geometry_assets import build_admin_boundaries_asset
from services.analytics.scripts.build_admin_boundaries_source import build_source_dataset

logger = logging.getLogger(__name__)

AnalyticsStepCallback = Callable[[str, int], None]

ANALYTICS_STEP_NAMES = [
    "bi_documents",
    "bi_locations",
    "bi_document_locations",
    "bi_location_hierarchy",
    "admin_boundaries_source",
    "admin_boundaries",
]


def build_admin_boundaries_source(_conn: Connection) -> int:
    source_path = Path(
        os.getenv(
            "DOCMAP_ADMIN_BOUNDARIES_SOURCE",
            str(Path(__file__).resolve().parent / "assets" / "admin_boundaries_source.geojson"),
        )
    )
    stats = build_source_dataset(source_path)
    return int(stats.get("total_features", 0))


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
            WITH typed_locations AS (
                SELECT
                    gl.id,
                    gl.normalized_location,
                    gl.country,
                    gl.region,
                    gl.city,
                    NULLIF(
                        BTRIM(
                            COALESCE(
                                (regexp_match(gl.normalized_location, ',\\s*([^,]+),\\s*[^,]+$'))[1],
                                ''
                            )
                        ),
                        ''
                    ) AS region_hint,
                    NULLIF(
                        BTRIM(
                            COALESCE(
                                (regexp_match(gl.normalized_location, '([^,]+)$'))[1],
                                ''
                            )
                        ),
                        ''
                    ) AS country_hint,
                    gl.latitude,
                    gl.longitude,
                    gl.precision,
                    COALESCE(
                        NULLIF(gl.location_rank, ''),
                        CASE
                            WHEN LOWER(gl.normalized_location) IN (
                                'africa',
                                'antarctica',
                                'asia',
                                'europe',
                                'north america',
                                'south america',
                                'oceania',
                                'australia'
                            ) THEN 'continent'
                            WHEN LOWER(gl.normalized_location) LIKE '%ocean%'
                                OR LOWER(gl.normalized_location) LIKE '%sea%'
                                OR LOWER(gl.normalized_location) LIKE '%gulf%'
                                OR LOWER(gl.normalized_location) LIKE '%strait%'
                                OR LOWER(gl.normalized_location) LIKE '%channel%'
                                OR LOWER(gl.normalized_location) LIKE '%bay%'
                            THEN 'ocean'
                            WHEN gl.city IS NOT NULL THEN 'city'
                            WHEN gl.region IS NOT NULL THEN 'admin_region'
                            WHEN gl.country IS NOT NULL THEN 'country'
                            ELSE 'unknown'
                        END
                    ) AS location_rank
                FROM geo_locations gl
            )
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
                    location_rank,
                    parent_location_id,
                    document_count
                )
            SELECT
                tl.id AS location_id,
                tl.normalized_location,
                tl.country,
                tl.region,
                tl.city,
                tl.latitude,
                tl.longitude,
                tl.precision,
                tl.location_rank,
                CASE
                    WHEN tl.location_rank = 'city' THEN
                        COALESCE(
                            (
                                SELECT parent.id
                                FROM typed_locations parent
                                WHERE
                                    parent.location_rank = 'admin_region'
                                    AND parent.city IS NULL
                                    AND COALESCE(tl.region, tl.region_hint) IS NOT NULL
                                    AND (
                                        parent.region = COALESCE(tl.region, tl.region_hint)
                                        OR LOWER(parent.normalized_location) = LOWER(COALESCE(tl.region_hint, tl.region))
                                    )
                                    AND (
                                        (parent.country = tl.country)
                                        OR (
                                            tl.country_hint IS NOT NULL
                                            AND LOWER(parent.normalized_location) = LOWER(tl.country_hint)
                                        )
                                        OR (parent.country IS NULL AND tl.country IS NULL)
                                    )
                                ORDER BY
                                    CASE
                                        WHEN LOWER(parent.normalized_location) = LOWER(COALESCE(tl.region_hint, tl.region)) THEN 0
                                        ELSE 1
                                    END,
                                    parent.normalized_location,
                                    parent.id
                                LIMIT 1
                            ),
                            (
                                SELECT parent.id
                                FROM typed_locations parent
                                WHERE
                                    parent.location_rank = 'country'
                                    AND parent.city IS NULL
                                    AND parent.region IS NULL
                                    AND COALESCE(tl.country, tl.country_hint) IS NOT NULL
                                    AND (
                                        parent.country = tl.country
                                        OR (
                                            tl.country_hint IS NOT NULL
                                            AND LOWER(parent.normalized_location) = LOWER(tl.country_hint)
                                        )
                                    )
                                ORDER BY
                                    CASE
                                        WHEN LOWER(parent.normalized_location) = LOWER(COALESCE(tl.country_hint, tl.country)) THEN 0
                                        ELSE 1
                                    END,
                                    parent.normalized_location,
                                    parent.id
                                LIMIT 1
                            )
                        )
                    WHEN tl.location_rank = 'admin_region' THEN
                        (
                            SELECT parent.id
                            FROM typed_locations parent
                            WHERE
                                parent.location_rank = 'country'
                                AND parent.city IS NULL
                                AND parent.region IS NULL
                                AND COALESCE(tl.country, tl.country_hint) IS NOT NULL
                                AND (
                                    parent.country = tl.country
                                    OR (
                                        tl.country_hint IS NOT NULL
                                        AND LOWER(parent.normalized_location) = LOWER(tl.country_hint)
                                    )
                                )
                            ORDER BY
                                CASE
                                    WHEN LOWER(parent.normalized_location) = LOWER(COALESCE(tl.country_hint, tl.country)) THEN 0
                                    ELSE 1
                                END,
                                parent.normalized_location,
                                parent.id
                            LIMIT 1
                        )
                    ELSE NULL
                END AS parent_location_id,
                COALESCE(docs.document_count, 0) AS document_count
            FROM typed_locations tl
            LEFT JOIN (
                SELECT location_id, COUNT(DISTINCT document_id) AS document_count
                FROM document_locations
                GROUP BY location_id
            ) docs ON docs.location_id = tl.id
            """
        )
        return cur.rowcount


def build_bi_document_locations(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_document_locations")
        cur.execute(
            """
            WITH RECURSIVE mention_rows AS (
                SELECT
                    dl.id AS document_location_id,
                    dl.document_id,
                    dl.location_id,
                    lm.evidence_quote
                FROM document_locations dl
                LEFT JOIN location_mentions lm ON lm.id = dl.mention_id
            ),
            expanded AS (
                SELECT
                    mr.document_location_id,
                    mr.document_id,
                    mr.location_id,
                    mr.evidence_quote,
                    0 AS depth
                FROM mention_rows mr

                UNION ALL

                SELECT
                    e.document_location_id,
                    e.document_id,
                    parent.parent_location_id AS location_id,
                    e.evidence_quote,
                    e.depth + 1 AS depth
                FROM expanded e
                JOIN bi_locations parent ON parent.location_id = e.location_id
                WHERE
                    parent.parent_location_id IS NOT NULL
                    AND parent.parent_location_id <> e.location_id
                    AND e.depth < 8
            ),
            rolled AS (
                SELECT DISTINCT
                    e.document_location_id,
                    e.document_id,
                    e.location_id,
                    e.evidence_quote
                FROM expanded e
            )
            INSERT INTO bi_document_locations
                (document_id, location_id, mention_count, evidence_quote)
            SELECT
                r.document_id,
                r.location_id,
                COUNT(*) AS mention_count,
                MIN(
                    CASE
                        WHEN r.evidence_quote IS NULL OR r.evidence_quote = '' THEN NULL
                        ELSE r.evidence_quote
                    END
                ) AS evidence_quote
            FROM rolled r
            GROUP BY r.document_id, r.location_id
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
        ("admin_boundaries_source", build_admin_boundaries_source),
        ("admin_boundaries", lambda conn: build_admin_boundaries_asset(conn).features_written),
    ]
    if start_index < 0:
        start_index = 0
    if start_index > len(steps):
        start_index = len(steps)

    documents_rows = 0
    locations_rows = 0
    links_rows = 0
    hierarchy_rows = 0
    admin_boundaries_source_rows = 0
    admin_boundaries_rows = 0
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
            elif name == "bi_location_hierarchy":
                hierarchy_rows = rows
            elif name == "admin_boundaries_source":
                admin_boundaries_source_rows = rows
            else:
                admin_boundaries_rows = rows
            if on_step:
                on_step(name, rows)
        conn.commit()

    stats = {
        "bi_documents": documents_rows,
        "bi_locations": locations_rows,
        "bi_document_locations": links_rows,
        "bi_location_hierarchy": hierarchy_rows,
        "admin_boundaries_source": admin_boundaries_source_rows,
        "admin_boundaries": admin_boundaries_rows,
    }
    logger.info("analytics.rebuild_done stats=%s", stats)
    return stats
