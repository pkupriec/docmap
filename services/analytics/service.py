from __future__ import annotations

import logging

from psycopg import Connection

from services.common.db import get_connection

logger = logging.getLogger(__name__)

def build_bi_documents(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_documents")
        cur.execute(
            """
            INSERT INTO bi_documents
                (document_id, scp_object_id, canonical_number, url, title, latest_snapshot_id, latest_snapshot_at, location_count)
            SELECT
                d.id AS document_id,
                d.scp_object_id,
                so.canonical_number,
                d.url,
                d.title,
                latest.id AS latest_snapshot_id,
                latest.created_at AS latest_snapshot_at,
                COALESCE(loc.location_count, 0) AS location_count
            FROM documents d
            LEFT JOIN scp_objects so ON so.id = d.scp_object_id
            LEFT JOIN LATERAL (
                SELECT ds.id, ds.created_at
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
                (location_id, normalized_location, country, region, city, latitude, longitude, precision, document_count)
            SELECT
                gl.id AS location_id,
                gl.normalized_location,
                gl.country,
                gl.region,
                gl.city,
                gl.latitude,
                gl.longitude,
                gl.precision,
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
                (document_id, location_id, mention_count)
            SELECT
                document_id,
                location_id,
                COUNT(*) AS mention_count
            FROM document_locations
            GROUP BY document_id, location_id
            """
        )
        return cur.rowcount


def rebuild_analytics() -> dict[str, int]:
    logger.info("analytics.rebuild_start")
    with get_connection() as conn:
        documents_rows = build_bi_documents(conn)
        locations_rows = build_bi_locations(conn)
        links_rows = build_bi_document_locations(conn)
        conn.commit()

    stats = {
        "bi_documents": documents_rows,
        "bi_locations": locations_rows,
        "bi_document_locations": links_rows,
    }
    logger.info("analytics.rebuild_done stats=%s", stats)
    return stats
