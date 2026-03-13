from __future__ import annotations

import json
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


@dataclass(frozen=True)
class GeoLocationCacheEntry:
    location_id: str
    location_rank: str | None
    osm_type: str | None
    osm_id: int | None
    osm_boundingbox: Any | None


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


def get_all_mentions(conn: Connection, *, limit: int = 1000, offset: int = 0) -> list[PendingMention]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT lm.id, ds.document_id, lm.normalized_location
            FROM location_mentions lm
            JOIN extraction_runs er ON er.id = lm.run_id
            JOIN document_snapshots ds ON ds.id = er.snapshot_id
            WHERE lm.normalized_location IS NOT NULL
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
    logger.info("geocoder.all_mentions_loaded count=%s limit=%s offset=%s", len(mentions), limit, offset)
    return mentions


def count_pending_mentions(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM location_mentions lm
            LEFT JOIN document_locations dl ON dl.mention_id = lm.id
            WHERE dl.id IS NULL
              AND lm.normalized_location IS NOT NULL
              AND btrim(lm.normalized_location) <> ''
            """
        )
        return int(cur.fetchone()[0])


def count_all_mentions(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM location_mentions lm
            WHERE lm.normalized_location IS NOT NULL
              AND btrim(lm.normalized_location) <> ''
            """
        )
        return int(cur.fetchone()[0])


def clear_document_links_for_all_mentions(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM document_locations dl
            USING location_mentions lm
            WHERE dl.mention_id = lm.id
              AND lm.normalized_location IS NOT NULL
              AND btrim(lm.normalized_location) <> ''
            """
        )
        return int(cur.rowcount or 0)


def get_geo_location_cache_entry(conn: Connection, normalized_location: str) -> GeoLocationCacheEntry | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, location_rank, osm_type, osm_id, osm_boundingbox
            FROM geo_locations
            WHERE normalized_location = %s
            """,
            (normalized_location,),
        )
        row = cur.fetchone()
        if not row:
            return None
        osm_id_raw = row[3]
        osm_id = int(osm_id_raw) if osm_id_raw is not None else None
        return GeoLocationCacheEntry(
            location_id=str(row[0]),
            location_rank=str(row[1]).strip() if row[1] is not None else None,
            osm_type=str(row[2]).strip() if row[2] is not None else None,
            osm_id=osm_id,
            osm_boundingbox=row[4],
        )


def get_geo_location_id_by_normalized_name(conn: Connection, normalized_location: str) -> str | None:
    entry = get_geo_location_cache_entry(conn, normalized_location)
    return entry.location_id if entry else None


def _geo_location_payload(location: dict[str, Any]) -> dict[str, Any]:
    boundingbox = location.get("osm_boundingbox")
    return {
        "normalized_location": location["normalized_location"],
        "country": location.get("country"),
        "region": location.get("region"),
        "city": location.get("city"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "precision": location.get("precision"),
        "location_rank": location.get("location_rank"),
        "osm_type": location.get("osm_type"),
        "osm_id": location.get("osm_id"),
        "osm_category": location.get("osm_category"),
        "osm_place_type": location.get("osm_place_type"),
        "osm_addresstype": location.get("osm_addresstype"),
        "osm_place_rank": location.get("osm_place_rank"),
        "osm_boundingbox_json": json.dumps(boundingbox) if boundingbox is not None else None,
    }


def save_geo_location(conn: Connection, location: dict[str, Any]) -> str:
    payload = _geo_location_payload(location)
    osm_type = payload.get("osm_type")
    osm_id = payload.get("osm_id")

    with conn.cursor() as cur:
        if osm_type and osm_id is not None:
            cur.execute(
                """
                SELECT id
                FROM geo_locations
                WHERE osm_type = %s
                  AND osm_id = %s
                LIMIT 1
                """,
                (osm_type, osm_id),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """
                    UPDATE geo_locations
                    SET
                        country = %s,
                        region = %s,
                        city = %s,
                        latitude = %s,
                        longitude = %s,
                        precision = %s,
                        location_rank = %s,
                        osm_category = %s,
                        osm_place_type = %s,
                        osm_addresstype = %s,
                        osm_place_rank = %s,
                        osm_boundingbox = %s::jsonb,
                        geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        payload["country"],
                        payload["region"],
                        payload["city"],
                        payload["latitude"],
                        payload["longitude"],
                        payload["precision"],
                        payload["location_rank"],
                        payload["osm_category"],
                        payload["osm_place_type"],
                        payload["osm_addresstype"],
                        payload["osm_place_rank"],
                        payload["osm_boundingbox_json"],
                        payload["longitude"],
                        payload["latitude"],
                        existing[0],
                    ),
                )
                return str(cur.fetchone()[0])

        cur.execute(
            """
            INSERT INTO geo_locations
                (
                    normalized_location,
                    country,
                    region,
                    city,
                    latitude,
                    longitude,
                    precision,
                    location_rank,
                    osm_type,
                    osm_id,
                    osm_category,
                    osm_place_type,
                    osm_addresstype,
                    osm_place_rank,
                    osm_boundingbox,
                    geom
                )
            VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                )
            ON CONFLICT (normalized_location) DO UPDATE
            SET country = EXCLUDED.country,
                region = EXCLUDED.region,
                city = EXCLUDED.city,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                precision = EXCLUDED.precision,
                location_rank = EXCLUDED.location_rank,
                osm_type = EXCLUDED.osm_type,
                osm_id = EXCLUDED.osm_id,
                osm_category = EXCLUDED.osm_category,
                osm_place_type = EXCLUDED.osm_place_type,
                osm_addresstype = EXCLUDED.osm_addresstype,
                osm_place_rank = EXCLUDED.osm_place_rank,
                osm_boundingbox = EXCLUDED.osm_boundingbox,
                geom = EXCLUDED.geom
            RETURNING id
            """,
            (
                payload["normalized_location"],
                payload["country"],
                payload["region"],
                payload["city"],
                payload["latitude"],
                payload["longitude"],
                payload["precision"],
                payload["location_rank"],
                payload["osm_type"],
                payload["osm_id"],
                payload["osm_category"],
                payload["osm_place_type"],
                payload["osm_addresstype"],
                payload["osm_place_rank"],
                payload["osm_boundingbox_json"],
                payload["longitude"],
                payload["latitude"],
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
