from __future__ import annotations

import json
from dataclasses import dataclass
import logging
import re
from typing import Any
import unicodedata

from psycopg import Connection

from services.geocoder.identity import location_identity_key

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
    geocode_candidates: Any | None = None
    boundary_intent: bool = False


SAFE_ALIAS_TYPES = ("exact_name", "language_variant")
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")


@dataclass(frozen=True)
class CanonicalResolution:
    canonical_id: str | None
    resolution_method: str
    confidence: int
    reason_code: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class _CanonicalAliasCandidate:
    canonical_id: str
    alias_type: str
    canonical_name: str
    parent_canonical_id: str | None
    country_canonical_id: str | None


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
    if normalized.startswith("admin_level_"):
        return "admin_region"
    if normalized == "region":
        return "admin_region"
    if normalized == "national_park":
        return "park"
    if normalized == "desert":
        return "desert"
    return normalized or "unknown"


def _alias_type_priority(alias_type: str | None) -> int:
    normalized = str(alias_type or "").strip().lower()
    if normalized == "exact_name":
        return 0
    if normalized == "language_variant":
        return 1
    return 9


def _load_alias_candidates(
    conn: Connection,
    *,
    normalized_alias: str,
    place_type: str,
) -> list[_CanonicalAliasCandidate]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                a.canonical_id,
                a.alias_type,
                p.canonical_name,
                p.parent_canonical_id,
                p.country_canonical_id
            FROM geo_canonical_aliases a
            JOIN geo_canonical_places p
              ON p.canonical_id = a.canonical_id
            WHERE a.normalized_alias = %s
              AND a.alias_type = ANY(%s)
              AND p.place_type = %s
            ORDER BY
                a.canonical_id,
                CASE a.alias_type
                    WHEN 'exact_name' THEN 0
                    WHEN 'language_variant' THEN 1
                    ELSE 9
                END
            """,
            (normalized_alias, list(SAFE_ALIAS_TYPES), place_type),
        )
        rows = cur.fetchall()

    deduped: dict[str, _CanonicalAliasCandidate] = {}
    for row in rows:
        canonical_id = str(row[0]).strip()
        alias_type = str(row[1]).strip().lower()
        candidate = _CanonicalAliasCandidate(
            canonical_id=canonical_id,
            alias_type=alias_type,
            canonical_name=str(row[2]).strip(),
            parent_canonical_id=str(row[3]).strip() if row[3] is not None else None,
            country_canonical_id=str(row[4]).strip() if row[4] is not None else None,
        )
        existing = deduped.get(canonical_id)
        if existing is None or _alias_type_priority(candidate.alias_type) < _alias_type_priority(existing.alias_type):
            deduped[canonical_id] = candidate
    return sorted(deduped.values(), key=lambda item: item.canonical_id)


def _load_alias_sets(
    conn: Connection,
    canonical_ids: list[str],
) -> dict[str, set[str]]:
    if not canonical_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT canonical_id, normalized_alias
            FROM geo_canonical_aliases
            WHERE canonical_id = ANY(%s)
              AND alias_type = ANY(%s)
            """,
            (canonical_ids, list(SAFE_ALIAS_TYPES)),
        )
        rows = cur.fetchall()
    alias_sets: dict[str, set[str]] = {candidate_id: set() for candidate_id in canonical_ids}
    for row in rows:
        candidate_id = str(row[0]).strip()
        normalized = _normalize_alias_text(row[1])
        if not normalized:
            continue
        alias_sets.setdefault(candidate_id, set()).add(normalized)
    return alias_sets


def _resolve_ambiguous_alias(
    conn: Connection,
    *,
    normalized_alias: str,
    payload: dict[str, Any],
    place_type: str,
    candidates: list[_CanonicalAliasCandidate],
) -> CanonicalResolution:
    candidate_ids = [candidate.canonical_id for candidate in candidates]
    alias_sets = _load_alias_sets(conn, candidate_ids)

    country_signal = _normalize_alias_text(payload.get("country"))
    region_signal = _normalize_alias_text(payload.get("region"))
    ambiguity_floor = 70
    ambiguity_gap = 20

    country_alias_sets: dict[str, set[str]] = {}
    country_ids = sorted({candidate.country_canonical_id for candidate in candidates if candidate.country_canonical_id})
    if country_ids:
        country_alias_sets = _load_alias_sets(conn, country_ids)

    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        score = 0
        score_breakdown: dict[str, int] = {}
        aliases = set(alias_sets.get(candidate.canonical_id, set()))
        candidate_name = _normalize_alias_text(candidate.canonical_name)
        if candidate_name:
            aliases.add(candidate_name)

        alias_weight = 35 if candidate.alias_type == "exact_name" else 25
        score += alias_weight
        score_breakdown["safe_alias_weight"] = alias_weight

        if candidate_name and candidate_name == normalized_alias:
            score += 10
            score_breakdown["canonical_name_exact"] = 10

        if place_type == "country" and country_signal and country_signal != normalized_alias:
            if country_signal in aliases:
                score += 55
                score_breakdown["country_signal_agreement"] = 55
            else:
                score -= 30
                score_breakdown["country_signal_conflict"] = -30

        if place_type == "admin_region":
            if region_signal and region_signal != normalized_alias:
                if region_signal in aliases:
                    score += 20
                    score_breakdown["region_signal_agreement"] = 20
                else:
                    score -= 15
                    score_breakdown["region_signal_conflict"] = -15
            if country_signal:
                parent_country_aliases = set()
                if candidate.country_canonical_id:
                    parent_country_aliases.update(country_alias_sets.get(candidate.country_canonical_id, set()))
                if country_signal in parent_country_aliases:
                    score += 45
                    score_breakdown["country_parent_agreement"] = 45
                elif parent_country_aliases:
                    score -= 25
                    score_breakdown["country_parent_conflict"] = -25

        scored.append(
            {
                "canonical_id": candidate.canonical_id,
                "score": score,
                "alias_type": candidate.alias_type,
                "score_breakdown": score_breakdown,
            }
        )

    scored.sort(key=lambda item: (-int(item["score"]), str(item["canonical_id"])))
    winner = scored[0]
    runner_up_score = int(scored[1]["score"]) if len(scored) > 1 else None
    winner_score = int(winner["score"])
    score_gap = winner_score - runner_up_score if runner_up_score is not None else winner_score

    details = {
        "reason_code": "deterministic_disambiguated",
        "input_alias": normalized_alias,
        "place_type": place_type,
        "signals": {
            "country": country_signal or None,
            "region": region_signal or None,
        },
        "thresholds": {"min_score": ambiguity_floor, "min_gap": ambiguity_gap},
        "winner_score": winner_score,
        "runner_up_score": runner_up_score,
        "score_gap": score_gap,
        "candidates": scored,
    }

    if winner_score < ambiguity_floor:
        details["reason_code"] = "ambiguous_alias_insufficient_signal"
        return CanonicalResolution(
            canonical_id=None,
            resolution_method="ambiguous_alias_insufficient_signal",
            confidence=0,
            reason_code="ambiguous_alias_insufficient_signal",
            details=details,
        )
    if runner_up_score is not None and score_gap < ambiguity_gap:
        details["reason_code"] = "ambiguous_alias_conflicting_signal"
        return CanonicalResolution(
            canonical_id=None,
            resolution_method="ambiguous_alias_conflicting_signal",
            confidence=0,
            reason_code="ambiguous_alias_conflicting_signal",
            details=details,
        )

    confidence = max(1, min(99, winner_score))
    return CanonicalResolution(
        canonical_id=str(winner["canonical_id"]),
        resolution_method="deterministic_ambiguity_resolver",
        confidence=confidence,
        reason_code="deterministic_disambiguated",
        details=details,
    )


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
                return CanonicalResolution(
                    canonical_id=str(row[0]),
                    resolution_method="osm_identity",
                    confidence=100,
                    reason_code="deterministic_disambiguated",
                    details={
                        "reason_code": "deterministic_disambiguated",
                        "strategy": "osm_identity",
                        "external_source": "osm",
                        "external_id": external_id,
                    },
                )

    normalized_alias = _normalize_alias_text(payload.get("normalized_location"))
    if not normalized_alias:
        return CanonicalResolution(
            canonical_id=None,
            resolution_method="none",
            confidence=0,
            reason_code="empty_alias",
            details={"reason_code": "empty_alias"},
        )
    place_type = _normalize_place_type(payload.get("location_rank"))
    candidates = _load_alias_candidates(conn, normalized_alias=normalized_alias, place_type=place_type)
    if len(candidates) == 1:
        alias_type = candidates[0].alias_type
        confidence = 75 if alias_type == "exact_name" else 65
        return CanonicalResolution(
            canonical_id=str(candidates[0].canonical_id),
            resolution_method="strict_alias",
            confidence=confidence,
            reason_code="deterministic_disambiguated",
            details={
                "reason_code": "deterministic_disambiguated",
                "strategy": "strict_alias",
                "input_alias": normalized_alias,
                "place_type": place_type,
                "alias_type": alias_type,
            },
        )
    if len(candidates) > 1:
        return _resolve_ambiguous_alias(
            conn,
            normalized_alias=normalized_alias,
            payload=payload,
            place_type=place_type,
            candidates=candidates,
        )
    return CanonicalResolution(
        canonical_id=None,
        resolution_method="none",
        confidence=0,
        reason_code="no_safe_alias_match",
        details={
            "reason_code": "no_safe_alias_match",
            "input_alias": normalized_alias,
            "place_type": place_type,
        },
    )


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
            SELECT gl.id, gl.location_rank, gl.osm_type, gl.osm_id, gl.osm_boundingbox,
                   gl.canonical_id, gl.geocode_candidates, gl.boundary_intent
            FROM geo_location_aliases a
            JOIN geo_locations gl ON gl.id = a.location_id
            WHERE a.normalized_location = %s
            """,
            (normalized_location,),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                SELECT id, location_rank, osm_type, osm_id, osm_boundingbox,
                       canonical_id, geocode_candidates, boundary_intent
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
            geocode_candidates=row[6],
            boundary_intent=bool(row[7]) if row[7] is not None else False,
        )


def get_geo_location_id_by_normalized_name(conn: Connection, normalized_location: str) -> str | None:
    entry = get_geo_location_cache_entry(conn, normalized_location)
    return entry.location_id if entry else None


def consolidate_location_identities(conn: Connection) -> dict[str, int]:
    """Backfill entity keys and redirect raw links without mutating analytics-owned tables."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                gl.id, gl.normalized_location, gl.country, gl.region, gl.latitude, gl.longitude,
                gl.precision, gl.location_rank, gl.osm_type, gl.osm_id, gl.canonical_id,
                gl.identity_key, COUNT(dl.id) AS link_count
            FROM geo_locations gl
            LEFT JOIN document_locations dl ON dl.location_id = gl.id
            GROUP BY gl.id
            ORDER BY gl.id
            """
        )
        rows = cur.fetchall()

        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            item = {
                "id": str(row[0]),
                "normalized_location": row[1],
                "country": row[2],
                "region": row[3],
                "latitude": row[4],
                "longitude": row[5],
                "precision": row[6],
                "location_rank": row[7],
                "osm_type": row[8],
                "osm_id": row[9],
                "canonical_id": row[10],
                "identity_key": row[11],
                "link_count": int(row[12] or 0),
            }
            key = location_identity_key(item)
            if key:
                groups.setdefault(key, []).append(item)

        redirected_links = 0
        duplicate_entities = 0
        for key, members in groups.items():
            members.sort(
                key=lambda item: (
                    0 if item["identity_key"] == key else 1,
                    0 if item["osm_type"] and item["osm_id"] is not None else 1,
                    0 if item["canonical_id"] else 1,
                    -int(item["link_count"]),
                    len(str(item["normalized_location"] or "")),
                    str(item["id"]),
                )
            )
            winner = members[0]
            cur.execute("UPDATE geo_locations SET identity_key = %s WHERE id = %s", (key, winner["id"]))
            for member in members:
                _save_location_alias(
                    cur,
                    normalized_location=str(member["normalized_location"]),
                    location_id=str(winner["id"]),
                )
            loser_ids = [str(item["id"]) for item in members[1:]]
            if loser_ids:
                cur.execute(
                    """
                    UPDATE document_locations
                    SET location_id = %s
                    WHERE location_id = ANY(%s::uuid[])
                    """,
                    (winner["id"], loser_ids),
                )
                redirected_links += int(cur.rowcount or 0)
                duplicate_entities += len(loser_ids)

    return {
        "identity_count": len(groups),
        "duplicate_entities": duplicate_entities,
        "redirected_links": redirected_links,
    }


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
        "osm_admin_level": location.get("osm_admin_level"),
        "osm_place_rank": location.get("osm_place_rank"),
        "osm_boundingbox_json": json.dumps(boundingbox) if boundingbox is not None else None,
        "boundary_intent": bool(location.get("boundary_intent", False)),
        "geocode_candidates_json": (
            json.dumps(location.get("geocode_candidates"))
            if location.get("geocode_candidates") is not None
            else None
        ),
        "canonical_id": location.get("canonical_id"),
        "canonical_resolution_method": location.get("canonical_resolution_method"),
        "canonical_confidence": location.get("canonical_confidence"),
        "canonical_resolution_details_json": (
            json.dumps(location.get("canonical_resolution_details"))
            if location.get("canonical_resolution_details") is not None
            else None
        ),
    }


def save_geo_location(conn: Connection, location: dict[str, Any]) -> str:
    payload = _geo_location_payload(location)
    canonical = _resolve_canonical_identity(conn, payload)
    payload["canonical_id"] = canonical.canonical_id
    payload["canonical_resolution_method"] = canonical.resolution_method
    payload["canonical_confidence"] = canonical.confidence
    payload["canonical_resolution_details"] = canonical.details
    payload["canonical_resolution_details_json"] = (
        json.dumps(canonical.details) if canonical.details is not None else None
    )
    osm_type = payload.get("osm_type")
    osm_id = payload.get("osm_id")
    identity_key = location_identity_key(payload)

    with conn.cursor() as cur:
        existing = None
        if identity_key:
            cur.execute(
                """
                SELECT id
                FROM geo_locations
                WHERE identity_key = %s
                LIMIT 1
                """,
                (identity_key,),
            )
            existing = cur.fetchone()
        if existing is None and osm_type and osm_id is not None:
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
                        osm_type = %s,
                        osm_id = %s,
                        osm_category = %s,
                        osm_place_type = %s,
                        osm_addresstype = %s,
                        osm_admin_level = %s,
                        osm_place_rank = %s,
                        osm_boundingbox = %s::jsonb,
                        boundary_intent = %s,
                        geocode_candidates = %s::jsonb,
                        canonical_id = %s,
                        canonical_resolution_method = %s,
                        canonical_confidence = %s,
                        canonical_resolution_details = %s::jsonb,
                        identity_key = %s,
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
                        payload["osm_type"],
                        payload["osm_id"],
                        payload["osm_category"],
                        payload["osm_place_type"],
                        payload["osm_addresstype"],
                        payload["osm_admin_level"],
                        payload["osm_place_rank"],
                        payload["osm_boundingbox_json"],
                        payload["boundary_intent"],
                        payload["geocode_candidates_json"],
                        payload["canonical_id"],
                        payload["canonical_resolution_method"],
                        payload["canonical_confidence"],
                        payload["canonical_resolution_details_json"],
                        identity_key,
                        payload["longitude"],
                        payload["latitude"],
                        existing[0],
                    ),
                )
            location_id = str(cur.fetchone()[0])
            _save_location_alias(cur, normalized_location=payload["normalized_location"], location_id=location_id)
            return location_id

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
                    osm_admin_level,
                    osm_place_rank,
                    osm_boundingbox,
                    boundary_intent,
                    geocode_candidates,
                    canonical_id,
                    canonical_resolution_method,
                    canonical_confidence,
                    canonical_resolution_details,
                    identity_key,
                    geom
                )
            VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s,
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
                osm_admin_level = EXCLUDED.osm_admin_level,
                osm_place_rank = EXCLUDED.osm_place_rank,
                osm_boundingbox = EXCLUDED.osm_boundingbox,
                boundary_intent = EXCLUDED.boundary_intent,
                geocode_candidates = EXCLUDED.geocode_candidates,
                canonical_id = EXCLUDED.canonical_id,
                canonical_resolution_method = EXCLUDED.canonical_resolution_method,
                canonical_confidence = EXCLUDED.canonical_confidence,
                canonical_resolution_details = EXCLUDED.canonical_resolution_details,
                identity_key = EXCLUDED.identity_key,
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
                payload["osm_admin_level"],
                payload["osm_place_rank"],
                payload["osm_boundingbox_json"],
                payload["boundary_intent"],
                payload["geocode_candidates_json"],
                payload["canonical_id"],
                payload["canonical_resolution_method"],
                payload["canonical_confidence"],
                payload["canonical_resolution_details_json"],
                identity_key,
                payload["longitude"],
                payload["latitude"],
            ),
        )
        location_id = str(cur.fetchone()[0])
        _save_location_alias(cur, normalized_location=payload["normalized_location"], location_id=location_id)
        return location_id


def _save_location_alias(cur, *, normalized_location: str, location_id: str) -> None:
    cur.execute(
        """
        INSERT INTO geo_location_aliases (normalized_location, location_id)
        VALUES (%s, %s)
        ON CONFLICT (normalized_location) DO UPDATE
        SET location_id = EXCLUDED.location_id
        """,
        (normalized_location, location_id),
    )


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
