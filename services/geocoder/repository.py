from __future__ import annotations

import json
from dataclasses import dataclass
import logging
import re
from typing import Any
import unicodedata

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
    canonical_id: str | None = None


SAFE_ALIAS_TYPES = ("exact_name", "language_variant")
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")


@dataclass(frozen=True)
class CanonicalResolution:
    canonical_id: str | None
    resolution_method: str
    confidence: int


def _normalize_alias_text(value: str | None) -> str:
    lowered = (value or "").strip().lower()
    if not lowered:
        return ""
    ascii_value = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.replace("&", " and ")
    ascii_value = NON_ALNUM_RE.sub(" ", ascii_value)
    return re.sub(r"\s+", " ", ascii_value).strip()


def _normalize_place_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "region":
        return "admin_region"
    return normalized or "unknown"


def _resolve_canonical_identity(conn: Connection, payload: dict[str, Any]) -> CanonicalResolution:
    osm_type = payload.get("osm_type")
    osm_id = payload.get("osm_id")
    if osm_type and osm_id is not None:
        external_id = f"{str(osm_type).strip().lower()}:{int(osm_id)}"
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT canonical_id
                FROM geo_canonical_concordances
                WHERE external_source = 'osm'
                  AND external_id = %s
                LIMIT 1
                """,
                (external_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return CanonicalResolution(canonical_id=str(row[0]), resolution_method="osm_identity", confidence=100)

    normalized_alias = _normalize_alias_text(payload.get("normalized_location"))
    if not normalized_alias:
        return CanonicalResolution(canonical_id=None, resolution_method="none", confidence=0)
    place_type = _normalize_place_type(payload.get("location_rank"))
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                a.canonical_id,
                a.alias_type
            FROM geo_canonical_aliases a
            JOIN geo_canonical_places p
              ON p.canonical_id = a.canonical_id
            WHERE a.normalized_alias = %s
              AND a.alias_type = ANY(%s)
              AND p.place_type = %s
            ORDER BY
                CASE a.alias_type
                    WHEN 'exact_name' THEN 0
                    WHEN 'language_variant' THEN 1
                    ELSE 9
                END,
                a.canonical_id
            LIMIT 2
            """,
            (normalized_alias, list(SAFE_ALIAS_TYPES), place_type),
        )
        rows = cur.fetchall()
    if len(rows) == 1 and rows[0][0]:
        alias_type = str(rows[0][1]).strip().lower()
        confidence = 75 if alias_type == "exact_name" else 65
        return CanonicalResolution(canonical_id=str(rows[0][0]), resolution_method="strict_alias", confidence=confidence)
    if len(rows) > 1:
        return CanonicalResolution(canonical_id=None, resolution_method="ambiguous_alias", confidence=0)
    return CanonicalResolution(canonical_id=None, resolution_method="none", confidence=0)


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
                 , canonical_id
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
            canonical_id=str(row[5]).strip() if row[5] is not None else None,
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
        "canonical_id": location.get("canonical_id"),
        "canonical_resolution_method": location.get("canonical_resolution_method"),
        "canonical_confidence": location.get("canonical_confidence"),
    }


def save_geo_location(conn: Connection, location: dict[str, Any]) -> str:
    payload = _geo_location_payload(location)
    canonical = _resolve_canonical_identity(conn, payload)
    payload["canonical_id"] = canonical.canonical_id
    payload["canonical_resolution_method"] = canonical.resolution_method
    payload["canonical_confidence"] = canonical.confidence
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
                        canonical_id = %s,
                        canonical_resolution_method = %s,
                        canonical_confidence = %s,
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
                        payload["canonical_id"],
                        payload["canonical_resolution_method"],
                        payload["canonical_confidence"],
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
                    canonical_id,
                    canonical_resolution_method,
                    canonical_confidence,
                    geom
                )
            VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s,
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
                canonical_id = EXCLUDED.canonical_id,
                canonical_resolution_method = EXCLUDED.canonical_resolution_method,
                canonical_confidence = EXCLUDED.canonical_confidence,
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
                payload["canonical_id"],
                payload["canonical_resolution_method"],
                payload["canonical_confidence"],
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
