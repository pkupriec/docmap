from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from psycopg import Connection

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class PendingMention:
    mention_id: str
    document_id: str
    normalized_location: str


def get_pending_mentions(conn: Connection, *, limit: int = 1000, offset: int = 0) -> list[PendingMention]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT lm.id, ds.document_id, lm.normalized_location
            FROM location_mentions lm
            JOIN extraction_runs er ON er.id = lm.run_id
            JOIN document_snapshots ds ON ds.id = er.snapshot_id
            LEFT JOIN document_locations dl ON dl.mention_id = lm.id
            WHERE dl.id IS NULL
              AND lm.normalized_location IS NOT NULL
              AND btrim(lm.normalized_location) <> ''
            ORDER BY lm.id
            LIMIT %s
            OFFSET %s
            """,
            (limit, offset),
        )
        rows = cur.fetchall()
    mentions = [
        PendingMention(
            mention_id=str(row[0]),
            document_id=str(row[1]),
            normalized_location=row[2],
        )
        for row in rows
    ]
    logger.info("geocoder.pending_mentions_loaded count=%s limit=%s offset=%s", len(mentions), limit, offset)
    return mentions


def get_geo_location_id_by_normalized_name(conn: Connection, normalized_location: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM geo_locations WHERE normalized_location = %s",
            (normalized_location,),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def save_geo_location(conn: Connection, location: dict[str, Any]) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO geo_locations
                (normalized_location, country, region, city, latitude, longitude, precision, geom)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)
            ON CONFLICT (normalized_location) DO UPDATE
            SET country = EXCLUDED.country,
                region = EXCLUDED.region,
                city = EXCLUDED.city,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                precision = EXCLUDED.precision,
                geom = EXCLUDED.geom
            RETURNING id
            """,
            (
                location["normalized_location"],
                location.get("country"),
                location.get("region"),
                location.get("city"),
                location.get("latitude"),
                location.get("longitude"),
                location.get("precision"),
                location.get("longitude"),
                location.get("latitude"),
            ),
        )
        return str(cur.fetchone()[0])


def link_document_location(conn: Connection, *, document_id: str, location_id: str, mention_id: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM document_locations WHERE mention_id = %s",
            (mention_id,),
        )
        existing = cur.fetchone()
        if existing:
            logger.info("geocoder.document_location_already_linked mention_id=%s", mention_id)
            return str(existing[0])

        cur.execute(
            """
            INSERT INTO document_locations (document_id, location_id, mention_id)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (document_id, location_id, mention_id),
        )
        return str(cur.fetchone()[0])
