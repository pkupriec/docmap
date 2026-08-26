from __future__ import annotations

import json
import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Literal
from typing import Any
from uuid import UUID

from services.common.db import get_connection

logger = logging.getLogger(__name__)
_WHITESPACE_RE = re.compile(r"\s+")
_BOUNDARY_ADMIN_LEVEL_RE = re.compile(r"^admin_level_(\d+)$")
_VIEWPORT_BUCKET_RE = re.compile(
    r"^(?P<band>world|regional|local):(?P<west>-?\d+):(?P<south>-?\d+):(?P<east>-?\d+):(?P<north>-?\d+)$"
)
_BOUNDARY_CHUNK_RE = re.compile(r"^(?P<band>world|regional|local):(?P<column>\d+):(?P<row>\d+)$")

RankFilter = Literal["default", "all"]
DEFAULT_BOUNDARY_RANKS: tuple[str, ...] = ("city", "admin_region", "country", "continent", "ocean")
VIEWPORT_BUCKET_SCHEMES: dict[str, tuple[int, int]] = {
    "world": (45, 30),
    "regional": (20, 12),
    "local": (8, 6),
}
BOUNDARY_CHUNK_SCHEMES: dict[str, tuple[int, int, int, int]] = {
    "world": (45, 30, 8, 6),
    "regional": (20, 12, 18, 15),
    "local": (8, 6, 45, 30),
}


@dataclass(frozen=True)
class ResolvedLocation:
    location_id: str
    depth: int
    location_rank: str


@dataclass(frozen=True)
class ScopedLocationDocuments:
    scope_rank: str
    location_count: int
    total_items: int
    items: list[dict[str, Any]]


@dataclass(frozen=True)
class ViewportBucket:
    bucket_id: str
    band: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class BoundaryChunk:
    chunk_id: str
    band: str
    column: int
    row: int
    bbox: tuple[float, float, float, float]


def _normalize_longitude(value: float) -> float:
    normalized = ((value + 180.0) % 360.0) - 180.0
    if math.isclose(normalized, -180.0) and value > 0:
        return 180.0
    return normalized


def parse_viewport_bucket(raw_bucket: str) -> ViewportBucket:
    match = _VIEWPORT_BUCKET_RE.match(str(raw_bucket).strip())
    if match is None:
        raise ValueError("viewport_bucket must match {world|regional|local}:west:south:east:north")

    band = match.group("band")
    lon_step, lat_step = VIEWPORT_BUCKET_SCHEMES[band]
    west = int(match.group("west"))
    south = int(match.group("south"))
    east = int(match.group("east"))
    north = int(match.group("north"))

    if west < -180 or west > 180 or east < -180 or east > 180:
        raise ValueError("viewport_bucket longitudes must stay within [-180, 180]")
    if south < -90 or south > 90 or north < -90 or north > 90 or south > north:
        raise ValueError("viewport_bucket latitudes must satisfy -90 <= south <= north <= 90")
    if west % lon_step != 0 or east % lon_step != 0:
        raise ValueError(f"viewport_bucket longitudes must align to the {band} longitude step")
    if south % lat_step != 0 or north % lat_step != 0:
        raise ValueError(f"viewport_bucket latitudes must align to the {band} latitude step")

    bucket_id = f"{band}:{west}:{south}:{east}:{north}"
    return ViewportBucket(
        bucket_id=bucket_id,
        band=band,
        bbox=(
            float(_normalize_longitude(float(west))),
            float(south),
            float(_normalize_longitude(float(east))),
            float(north),
        ),
    )


def parse_boundary_chunk(raw_chunk: str) -> BoundaryChunk:
    match = _BOUNDARY_CHUNK_RE.match(str(raw_chunk).strip())
    if match is None:
        raise ValueError("chunk_ids entries must match {world|regional|local}:column:row")

    band = match.group("band")
    lon_step, lat_step, lon_cells, lat_cells = BOUNDARY_CHUNK_SCHEMES[band]
    column = int(match.group("column"))
    row = int(match.group("row"))

    if column < 0 or column >= lon_cells:
        raise ValueError(f"chunk_ids column must stay within [0, {lon_cells - 1}] for {band}")
    if row < 0 or row >= lat_cells:
        raise ValueError(f"chunk_ids row must stay within [0, {lat_cells - 1}] for {band}")

    west = -180 + column * lon_step
    east = west + lon_step
    south = -90 + row * lat_step
    north = south + lat_step
    return BoundaryChunk(
        chunk_id=f"{band}:{column}:{row}",
        band=band,
        column=column,
        row=row,
        bbox=(float(west), float(south), float(_normalize_longitude(float(east))), float(north)),
    )


class PresentationRepository:
    def _normalize_text(self, value: object | None) -> str:
        return _WHITESPACE_RE.sub(" ", str(value or "").strip().lower())

    def _normalize_rank(self, rank: object | None) -> str:
        value = str(rank or "unknown").strip().lower()
        if value == "region":
            return "admin_region"
        return value or "unknown"

    def _boundary_rank_sort_value(self, rank: str) -> int:
        normalized = self._normalize_rank(rank)
        if normalized == "ocean":
            return 0
        if normalized == "continent":
            return 1
        if normalized == "country":
            return 2
        if normalized == "admin_region":
            return 3
        if normalized == "city":
            return 4
        if normalized in {"national_park", "desert"}:
            return 5
        admin_level = _BOUNDARY_ADMIN_LEVEL_RE.match(normalized)
        if admin_level is not None:
            return 10 + int(admin_level.group(1))
        if normalized == "unknown":
            return 90
        return 99

    def _normalize_boundary_ranks(
        self,
        ranks: tuple[str, ...] | list[str] | None,
        *,
        rank_filter: RankFilter,
    ) -> tuple[str, ...] | None:
        if ranks:
            canonical = {self._normalize_rank(rank) for rank in ranks if str(rank).strip()}
            return tuple(sorted(canonical, key=lambda value: (self._boundary_rank_sort_value(value), value)))
        if rank_filter == "all":
            return None
        return DEFAULT_BOUNDARY_RANKS

    def _normalize_boundary_location_ids(
        self,
        *,
        selected_location_id: str | UUID | None,
        highlighted_location_ids: tuple[str, ...] | list[str] | None,
    ) -> tuple[str, ...]:
        explicit_ids = {
            str(location_id)
            for location_id in [selected_location_id, *(highlighted_location_ids or [])]
            if location_id is not None and str(location_id).strip()
        }
        return tuple(sorted(explicit_ids))

    def _resolve_boundary_bbox(
        self,
        *,
        chunk_ids: tuple[str, ...] | list[str] | None,
        viewport_bucket: str | None,
        bbox: tuple[float, float, float, float] | None,
    ) -> tuple[tuple[str, ...], str | None, tuple[float, float, float, float] | None, tuple[tuple[float, float, float, float], ...]]:
        normalized_chunk_ids = tuple(sorted({parse_boundary_chunk(chunk_id).chunk_id for chunk_id in chunk_ids or ()}))
        if normalized_chunk_ids and (viewport_bucket or bbox is not None):
            raise ValueError("chunk_ids cannot be combined with viewport_bucket or bbox")
        if viewport_bucket and bbox is not None:
            raise ValueError("viewport_bucket and bbox are mutually exclusive")
        if normalized_chunk_ids:
            return (
                normalized_chunk_ids,
                None,
                None,
                tuple(parse_boundary_chunk(chunk_id).bbox for chunk_id in normalized_chunk_ids),
            )
        if viewport_bucket:
            parsed = parse_viewport_bucket(viewport_bucket)
            return (), parsed.bucket_id, parsed.bbox, ()
        return (), None, bbox, ()

    def _semantic_city_key(self, row: dict[str, Any]) -> tuple[str, str, str, float, float] | None:
        precision = self._normalize_text(row.get("precision"))
        if precision != "city":
            return None
        latitude = row.get("latitude")
        longitude = row.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            return None
        if not math.isfinite(float(latitude)) or not math.isfinite(float(longitude)):
            return None

        region = self._normalize_text(row.get("region"))
        country = self._normalize_text(row.get("country"))
        parts = [self._normalize_text(part) for part in str(row.get("name") or row.get("normalized_location") or "").split(",")]
        parts = [part for part in parts if part]
        removable = {region, country}
        while parts and parts[-1] in removable:
            parts.pop()
        base_name = ", ".join(parts)
        if not base_name:
            return None
        return (base_name, region, country, round(float(latitude), 5), round(float(longitude), 5))

    def _location_row_sort_key(self, row: dict[str, Any]) -> tuple[Any, ...]:
        name = str(row.get("name") or row.get("normalized_location") or "")
        rank = self._normalize_rank(row.get("location_rank"))
        return (
            int(row.get("rank_bucket") or 99),
            -int(row.get("document_count") or 0),
            0 if rank != "unknown" else 1,
            len(name),
            name.lower(),
            str(row.get("location_id") or ""),
        )

    def _reduce_semantic_city_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str, float, float], list[dict[str, Any]]] = {}
        passthrough: list[dict[str, Any]] = []
        for row in rows:
            key = self._semantic_city_key(row)
            if key is None:
                passthrough.append(row)
                continue
            grouped.setdefault(key, []).append(row)

        reduced = passthrough[:]
        for group_rows in grouped.values():
            if len(group_rows) == 1:
                reduced.append(group_rows[0])
                continue
            preferred = min(group_rows, key=self._location_row_sort_key)
            merged = dict(preferred)
            merged["document_count"] = sum(int(item.get("document_count") or 0) for item in group_rows)
            reduced.append(merged)

        reduced.sort(key=self._location_row_sort_key)
        return reduced

    def _get_location_row(self, location_id: Any) -> dict[str, Any] | None:
        sql = """
            SELECT
                bl.location_id,
                bl.normalized_location,
                bl.country,
                bl.region,
                bl.city,
                bl.latitude,
                bl.longitude,
                bl.precision,
                bl.location_rank,
                COALESCE(bl.document_count, 0) AS document_count
            FROM bi_locations bl
            WHERE bl.location_id = %(location_id)s
            LIMIT 1
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"location_id": location_id})
                row = cur.fetchone()
                columns = [d[0] for d in cur.description] if row is not None else []
        if row is None:
            return None
        payload = dict(zip(columns, row, strict=True))
        payload["name"] = payload["normalized_location"]
        return payload

    def _list_semantic_city_peer_rows(self, location_row: dict[str, Any]) -> list[dict[str, Any]]:
        key = self._semantic_city_key(location_row)
        if key is None:
            return [location_row]
        sql = """
            SELECT
                bl.location_id,
                bl.normalized_location,
                bl.country,
                bl.region,
                bl.city,
                bl.latitude,
                bl.longitude,
                bl.precision,
                bl.location_rank,
                COALESCE(bl.document_count, 0) AS document_count
            FROM bi_locations bl
            WHERE
                bl.precision = 'city'
                AND LOWER(COALESCE(bl.country, '')) = LOWER(COALESCE(%(country)s, ''))
                AND LOWER(COALESCE(bl.region, '')) = LOWER(COALESCE(%(region)s, ''))
                AND ROUND(CAST(bl.latitude AS numeric), 5) = ROUND(CAST(%(latitude)s AS numeric), 5)
                AND ROUND(CAST(bl.longitude AS numeric), 5) = ROUND(CAST(%(longitude)s AS numeric), 5)
            ORDER BY bl.location_id ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    {
                        "country": location_row.get("country"),
                        "region": location_row.get("region"),
                        "latitude": location_row.get("latitude"),
                        "longitude": location_row.get("longitude"),
                    },
                )
                columns = [d[0] for d in cur.description]
                rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
        for row in rows:
            row["name"] = row["normalized_location"]
        peers = [row for row in rows if self._semantic_city_key(row) == key]
        if not peers:
            return [location_row]
        peers.sort(key=self._location_row_sort_key)
        return peers

    def get_semantic_scope_location_ids(self, location_id: Any, *, scope_rank: str) -> list[str]:
        if str(scope_rank).lower() != "city":
            return []
        location_row = self._get_location_row(location_id)
        if location_row is None:
            return []
        return [str(row["location_id"]) for row in self._list_semantic_city_peer_rows(location_row)]

    def _geometry_supported(self, geometry: object) -> bool:
        if not isinstance(geometry, dict):
            return False
        return geometry.get("type") in {"Polygon", "MultiPolygon"}

    def _parse_feature_row(self, payload: object) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            parsed = payload
        elif isinstance(payload, (str, bytes, bytearray)):
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                return None
            if not isinstance(parsed, dict):
                return None
        else:
            return None
        geometry = parsed.get("geometry")
        if not self._geometry_supported(geometry):
            return None
        return parsed

    def _serialize_feature(
        self,
        parsed: dict[str, Any],
        *,
        minimal: bool,
    ) -> dict[str, Any] | None:
        geometry = parsed.get("geometry")
        if not isinstance(geometry, dict):
            return None
        raw_properties = parsed.get("properties")
        properties = raw_properties if isinstance(raw_properties, dict) else {}
        if minimal:
            return {
                "type": "Feature",
                "properties": {
                    "location_id": properties.get("location_id"),
                    "location_name": properties.get("location_name"),
                    "location_rank": properties.get("location_rank"),
                    "country_name": properties.get("country_name"),
                    "region_name": properties.get("region_name"),
                    "aliases": properties.get("aliases"),
                    "safe_aliases": properties.get("safe_aliases"),
                    "country_aliases": properties.get("country_aliases"),
                    "region_aliases": properties.get("region_aliases"),
                    "match_strategy": properties.get("match_strategy"),
                },
                "geometry": {
                    "type": geometry.get("type"),
                    "coordinates": geometry.get("coordinates"),
                },
            }
        return {
            "type": "Feature",
            "properties": properties,
            "geometry": {
                "type": geometry.get("type"),
                "coordinates": geometry.get("coordinates"),
            },
        }

    def get_admin_boundaries_geojson(
        self,
        *,
        minimal: bool = False,
        rank_filter: RankFilter = "default",
        ranks: tuple[str, ...] | list[str] | None = None,
        chunk_ids: tuple[str, ...] | list[str] | None = None,
        viewport_bucket: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        selected_location_id: str | UUID | None = None,
        highlighted_location_ids: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, Any]:
        total_start = time.perf_counter()
        normalized_ranks = self._normalize_boundary_ranks(ranks, rank_filter=rank_filter)
        normalized_chunk_ids, normalized_viewport_bucket, resolved_bbox, resolved_chunk_bboxes = self._resolve_boundary_bbox(
            chunk_ids=chunk_ids,
            viewport_bucket=viewport_bucket,
            bbox=bbox,
        )
        explicit_location_ids = self._normalize_boundary_location_ids(
            selected_location_id=selected_location_id,
            highlighted_location_ids=highlighted_location_ids,
        )

        params: list[Any] = []
        rank_sql = ""
        if normalized_ranks is not None:
            rank_sql = "location_rank = ANY(%s::text[])"
            params.append(list(normalized_ranks))

        def append_bbox_clause(bounds: tuple[float, float, float, float]) -> str:
            west, south, east, north = bounds
            lat_clause = "(max_lat >= %s AND min_lat <= %s)"
            params.extend([south, north])
            if west <= east:
                lon_clause = "(max_lon >= %s AND min_lon <= %s)"
                params.extend([west, east])
            else:
                lon_clause = "((max_lon >= %s) OR (min_lon <= %s))"
                params.extend([west, east])
            return f"({lat_clause} AND {lon_clause})"

        spatial_domains: list[str] = []
        if resolved_chunk_bboxes:
            spatial_domains.extend(append_bbox_clause(bounds) for bounds in resolved_chunk_bboxes)
        elif resolved_bbox is not None:
            spatial_domains.append(append_bbox_clause(resolved_bbox))

        where_clauses: list[str] = []
        if spatial_domains:
            if rank_sql:
                where_clauses.append(f"({rank_sql} AND ({' OR '.join(spatial_domains)}))")
            else:
                where_clauses.append(f"({' OR '.join(spatial_domains)})")
        elif rank_sql:
            where_clauses.append(f"({rank_sql})")
        if explicit_location_ids:
            where_clauses.append("location_id = ANY(%s::uuid[])")
            params.append(list(explicit_location_ids))

        where_sql = f"WHERE {' OR '.join(where_clauses)}" if where_clauses else ""
        sql = f"""
            SELECT feature_json
            FROM bi_admin_boundaries
            {where_sql}
            ORDER BY
                CASE location_rank
                    WHEN 'ocean' THEN 0
                    WHEN 'continent' THEN 1
                    WHEN 'country' THEN 2
                    WHEN 'admin_region' THEN 3
                    WHEN 'city' THEN 4
                    WHEN 'national_park' THEN 5
                    WHEN 'desert' THEN 5
                    ELSE 99
                END,
                location_id ASC
        """
        db_start = time.perf_counter()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        db_elapsed_ms = (time.perf_counter() - db_start) * 1000.0
        transform_start = time.perf_counter()
        features: list[dict[str, Any]] = []
        seen_location_ids: set[str] = set()
        for row in rows:
            parsed = self._parse_feature_row(row[0] if row else None)
            if parsed is None:
                continue
            properties = parsed.get("properties")
            if not isinstance(properties, dict):
                continue
            location_id = str(properties.get("location_id") or "").strip()
            if location_id:
                if location_id in seen_location_ids:
                    continue
                seen_location_ids.add(location_id)
            serialized = self._serialize_feature(
                parsed,
                minimal=minimal,
            )
            if serialized is None:
                continue
            features.append(serialized)
        total_elapsed_ms = (time.perf_counter() - total_start) * 1000.0
        transform_elapsed_ms = (time.perf_counter() - transform_start) * 1000.0
        logger.info(
            "presentation.boundaries_repo_fetch minimal=%s rank_filter=%s ranks=%s bbox=%s explicit_ids=%s rows=%s features=%s db_ms=%.2f transform_ms=%.2f total_ms=%.2f",
            minimal,
            rank_filter,
            normalized_ranks,
            normalized_chunk_ids or normalized_viewport_bucket or resolved_bbox,
            len(explicit_location_ids),
            len(rows),
            len(features),
            db_elapsed_ms,
            transform_elapsed_ms,
            total_elapsed_ms,
        )
        return {
            "type": "FeatureCollection",
            "features": features,
        }

    def list_locations(self) -> list[dict[str, Any]]:
        start = time.perf_counter()
        sql = """
            SELECT
                bl.location_id,
                bl.normalized_location AS name,
                bl.latitude,
                bl.longitude,
                bl.precision,
                bl.location_rank,
                bl.document_count,
                bl.parent_location_id
            FROM bi_locations bl
            WHERE
                bl.latitude IS NOT NULL
                AND bl.longitude IS NOT NULL
                AND bl.latitude = bl.latitude
                AND bl.longitude = bl.longitude
                AND bl.latitude BETWEEN -90 AND 90
                AND bl.longitude BETWEEN -180 AND 180
            ORDER BY bl.document_count DESC, bl.normalized_location ASC, bl.location_id ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
        reduced_rows = self._reduce_semantic_city_rows([dict(zip(columns, row, strict=True)) for row in rows])
        logger.info(
            "presentation.locations_repo_fetch rows=%s reduced_rows=%s total_ms=%.2f",
            len(rows),
            len(reduced_rows),
            (time.perf_counter() - start) * 1000.0,
        )
        return reduced_rows

    def resolve_location_for_documents(self, location_id: Any) -> ResolvedLocation | None:
        start = time.perf_counter()
        requested_row = self._get_location_row(location_id)
        if requested_row is not None and self._semantic_city_key(requested_row) is not None:
            semantic_peers = self._list_semantic_city_peer_rows(requested_row)
            preferred = semantic_peers[0]
            fallback_depth = 0 if str(preferred["location_id"]) == str(location_id) else 1
            resolved = ResolvedLocation(
                location_id=str(preferred["location_id"]),
                depth=fallback_depth,
                location_rank="city",
            )
            logger.info(
                "presentation.resolve_location_for_documents requested_location_id=%s resolved_location_id=%s depth=%s scope_rank=%s semantic_peer_count=%s total_ms=%.2f",
                location_id,
                resolved.location_id,
                resolved.depth,
                resolved.location_rank,
                len(semantic_peers),
                (time.perf_counter() - start) * 1000.0,
            )
            return resolved

        sql = """
            WITH requested AS (
                SELECT
                    bl.location_id,
                    bl.normalized_location,
                    bl.country,
                    bl.region,
                    COALESCE(NULLIF(LOWER(bl.location_rank), ''), 'unknown') AS location_rank
                FROM bi_locations bl
                WHERE bl.location_id = %(location_id)s
            ),
            ranked_candidates AS (
                SELECT
                    r.location_id,
                    r.location_rank,
                    0 AS alias_depth
                FROM requested r

                UNION
                SELECT
                    peer.location_id,
                    COALESCE(NULLIF(LOWER(peer.location_rank), ''), 'unknown') AS location_rank,
                    1 AS alias_depth
                FROM requested r
                JOIN bi_locations peer
                    ON r.location_rank = 'country'
                    AND COALESCE(NULLIF(LOWER(peer.location_rank), ''), 'unknown') = 'country'
                    AND peer.location_id <> r.location_id
                    AND LOWER(COALESCE(peer.country, '')) = LOWER(COALESCE(r.country, ''))

                UNION
                SELECT
                    peer.location_id,
                    COALESCE(NULLIF(LOWER(peer.location_rank), ''), 'unknown') AS location_rank,
                    1 AS alias_depth
                FROM requested r
                JOIN bi_locations peer
                    ON r.location_rank IN ('admin_region', 'region')
                    AND COALESCE(NULLIF(LOWER(peer.location_rank), ''), 'unknown') IN ('admin_region', 'region')
                    AND peer.location_id <> r.location_id
                    AND LOWER(COALESCE(peer.country, '')) = LOWER(COALESCE(r.country, ''))
                    AND LOWER(COALESCE(peer.region, peer.normalized_location, ''))
                        = LOWER(COALESCE(r.region, r.normalized_location, ''))
            ),
            scored_candidates AS (
                SELECT
                    c.location_id,
                    c.location_rank,
                    c.alias_depth,
                    EXISTS (
                        SELECT 1
                        FROM bi_document_locations bdl
                        WHERE bdl.location_id = c.location_id
                    ) AS has_docs,
                    COALESCE(bl.document_count, 0) AS document_count
                FROM ranked_candidates c
                JOIN bi_locations bl ON bl.location_id = c.location_id
            ),
            ordered AS (
                SELECT
                    sc.location_id,
                    sc.location_rank,
                    sc.alias_depth,
                    ROW_NUMBER() OVER (
                        ORDER BY
                            CASE
                                WHEN sc.alias_depth = 0 AND sc.has_docs THEN 0
                                WHEN sc.alias_depth > 0 AND sc.has_docs THEN 1
                                WHEN sc.alias_depth = 0 THEN 2
                                ELSE 3
                            END,
                            sc.document_count DESC,
                            sc.location_id ASC
                    ) AS rn
                FROM scored_candidates sc
            )
            SELECT
                o.location_id,
                o.alias_depth,
                o.location_rank
            FROM ordered o
            WHERE o.rn = 1
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"location_id": location_id})
                row = cur.fetchone()
        if row is None:
            logger.info(
                "presentation.resolve_location_for_documents requested_location_id=%s resolved_location_id=None total_ms=%.2f",
                location_id,
                (time.perf_counter() - start) * 1000.0,
            )
            return None
        resolved = ResolvedLocation(location_id=str(row[0]), depth=int(row[1]), location_rank=str(row[2]))
        logger.info(
            "presentation.resolve_location_for_documents requested_location_id=%s resolved_location_id=%s depth=%s scope_rank=%s total_ms=%.2f",
            location_id,
            resolved.location_id,
            resolved.depth,
            resolved.location_rank,
            (time.perf_counter() - start) * 1000.0,
        )
        return resolved

    def get_location_name(self, location_id: Any) -> str | None:
        sql = """
            SELECT bl.normalized_location
            FROM bi_locations bl
            WHERE bl.location_id = %(location_id)s
            LIMIT 1
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"location_id": location_id})
                row = cur.fetchone()
        if row is None:
            return None
        return str(row[0])

    def list_location_documents(
        self,
        location_id: Any,
        *,
        scope_rank: str,
        limit: int,
        offset: int,
        semantic_scope_location_ids: list[Any] | None = None,
    ) -> ScopedLocationDocuments:
        scope_rank_normalized = str(scope_rank).lower()
        start = time.perf_counter()
        if scope_rank_normalized == "region":
            scope_rank_normalized = "admin_region"

        city_scope_ids = [str(item) for item in semantic_scope_location_ids or [] if item is not None]
        if scope_rank_normalized == "city" and city_scope_ids:
            scope_locations_sql = """
                SELECT DISTINCT UNNEST(%s::uuid[]) AS location_id
            """
            base_params: list[Any] = [city_scope_ids]
        else:
            if scope_rank_normalized == "city":
                rank_filter = ("city",)
            else:
                rank_filter = ()

            rank_filter_sql = ", ".join(["%s"] * len(rank_filter)) if rank_filter else ""
            rank_clause = (
                f"AND COALESCE(NULLIF(LOWER(bl.location_rank), ''), 'unknown') IN ({rank_filter_sql})"
                if rank_filter
                else ""
            )
            scope_locations_sql = f"""
                SELECT
                    h.descendant_location_id AS location_id
                FROM bi_location_hierarchy h
                JOIN bi_locations bl ON bl.location_id = h.descendant_location_id
                WHERE
                    h.ancestor_location_id = %s
                    {rank_clause}
            """
            base_params = [location_id, *rank_filter]

        scope_sql = f"""
            WITH scope_locations AS (
                {scope_locations_sql}
            ),
            scope_counts AS (
                SELECT COUNT(DISTINCT sl.location_id) AS location_count
                FROM scope_locations sl
            ),
            scoped_docs AS (
                SELECT DISTINCT bdl.document_id
                FROM bi_document_locations bdl
                JOIN scope_locations sl ON sl.location_id = bdl.location_id
            ),
            doc_counts AS (
                SELECT COUNT(*) AS total_items
                FROM scoped_docs
            ),
            page_docs AS (
                SELECT sd.document_id
                FROM scoped_docs sd
                JOIN bi_documents bd ON bd.document_id = sd.document_id
                ORDER BY
                    CASE WHEN bd.canonical_number IS NULL THEN 1 ELSE 0 END ASC,
                    bd.canonical_number ASC,
                    bd.url ASC,
                    bd.document_id ASC
                LIMIT %s
                OFFSET %s
            )
            SELECT
                bd.document_id,
                COALESCE(bd.canonical_number, '') AS scp_number,
                COALESCE(LOWER(bd.canonical_number), '') AS canonical_scp_id,
                bd.url AS scp_url,
                CASE
                    WHEN bd.latest_snapshot_id IS NOT NULL THEN '/api/map/document/' || bd.document_id || '/pdf'
                    ELSE NULL
                END AS pdf_url,
                dc.total_items,
                sc.location_count
            FROM page_docs pd
            JOIN bi_documents bd ON bd.document_id = pd.document_id
            CROSS JOIN doc_counts dc
            CROSS JOIN scope_counts sc
            ORDER BY
                CASE WHEN bd.canonical_number IS NULL THEN 1 ELSE 0 END ASC,
                bd.canonical_number ASC,
                bd.url ASC,
                bd.document_id ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(scope_sql, [*base_params, limit, offset])
                columns = [d[0] for d in cur.description]
                rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]

                cur.execute(
                    f"""
                    WITH scope_locations AS (
                        {scope_locations_sql}
                    )
                    SELECT COUNT(DISTINCT sl.location_id) AS location_count
                    FROM scope_locations sl
                    """,
                    base_params,
                )
                scope_row = cur.fetchone()
                location_count = int(scope_row[0]) if scope_row is not None and scope_row[0] is not None else 0

                cur.execute(
                    f"""
                    WITH scope_locations AS (
                        {scope_locations_sql}
                    ),
                    scoped_docs AS (
                        SELECT DISTINCT bdl.document_id
                        FROM bi_document_locations bdl
                        JOIN scope_locations sl ON sl.location_id = bdl.location_id
                    )
                    SELECT COUNT(*) AS total_items
                    FROM scoped_docs
                    """,
                    base_params,
                )
                count_row = cur.fetchone()
                total_items = int(count_row[0]) if count_row is not None and count_row[0] is not None else 0

        items = [
            {
                "document_id": row["document_id"],
                "scp_number": row["scp_number"],
                "canonical_scp_id": row["canonical_scp_id"],
                "scp_url": row["scp_url"],
                "pdf_url": row["pdf_url"],
            }
            for row in rows
        ]
        logger.info(
            "presentation.location_documents_repo_fetch location_id=%s scope_rank=%s semantic_scope_size=%s location_count=%s total_items=%s returned_items=%s limit=%s offset=%s total_ms=%.2f",
            location_id,
            scope_rank_normalized,
            len(city_scope_ids),
            location_count,
            total_items,
            len(items),
            limit,
            offset,
            (time.perf_counter() - start) * 1000.0,
        )
        return ScopedLocationDocuments(
            scope_rank=scope_rank_normalized,
            location_count=location_count,
            total_items=total_items,
            items=items,
        )

    def list_document_locations(self, document_id: Any) -> list[dict[str, Any]]:
        start = time.perf_counter()
        sql = """
            SELECT
                bdl.document_id,
                bl.location_id,
                bl.normalized_location AS name,
                bl.latitude,
                bl.longitude,
                bl.precision,
                bl.location_rank,
                bdl.evidence_quote,
                bdl.mention_count
            FROM bi_document_locations bdl
            JOIN bi_locations bl ON bl.location_id = bdl.location_id
            WHERE bdl.document_id = %(document_id)s
                AND bl.latitude IS NOT NULL
                AND bl.longitude IS NOT NULL
                AND bl.latitude = bl.latitude
                AND bl.longitude = bl.longitude
                AND bl.latitude BETWEEN -90 AND 90
                AND bl.longitude BETWEEN -180 AND 180
            ORDER BY bdl.mention_count DESC, bl.normalized_location ASC, bl.location_id ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"document_id": document_id})
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
        payload = [dict(zip(columns, row, strict=True)) for row in rows]
        logger.info(
            "presentation.document_locations_repo_fetch document_id=%s rows=%s total_ms=%.2f",
            document_id,
            len(payload),
            (time.perf_counter() - start) * 1000.0,
        )
        return payload

    def list_density_points(self) -> list[dict[str, Any]]:
        sql = """
            SELECT
                bl.latitude,
                bl.longitude,
                bl.document_count
            FROM bi_locations bl
            WHERE
                bl.latitude IS NOT NULL
                AND bl.longitude IS NOT NULL
                AND bl.latitude = bl.latitude
                AND bl.longitude = bl.longitude
                AND bl.latitude BETWEEN -90 AND 90
                AND bl.longitude BETWEEN -180 AND 180
            ORDER BY bl.document_count DESC, bl.location_id ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def get_document_card(self, document_id: UUID) -> dict[str, Any] | None:
        sql = """
            WITH top_location AS (
                SELECT
                    bdl.document_id,
                    bl.normalized_location AS location_display,
                    ROW_NUMBER() OVER (
                        PARTITION BY bdl.document_id
                        ORDER BY bdl.mention_count DESC, bl.normalized_location ASC, bl.location_id ASC
                    ) AS rn
                FROM bi_document_locations bdl
                JOIN bi_locations bl ON bl.location_id = bdl.location_id
            )
            SELECT
                bd.document_id,
                COALESCE(bd.canonical_number, '') AS scp_number,
                COALESCE(LOWER(bd.canonical_number), '') AS canonical_scp_id,
                bd.url AS scp_url,
                tl.location_display,
                CASE
                    WHEN bd.latest_snapshot_id IS NOT NULL THEN '/api/map/document/' || bd.document_id || '/pdf'
                    ELSE NULL
                END AS pdf_url
            FROM bi_documents bd
            LEFT JOIN top_location tl
                ON tl.document_id = bd.document_id
                AND tl.rn = 1
            WHERE bd.document_id = %(document_id)s
            LIMIT 1
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"document_id": document_id})
                row = cur.fetchone()
                columns = [d[0] for d in cur.description] if row is not None else []
        if row is None:
            return None
        return dict(zip(columns, row, strict=True))

    def get_document_pdf(self, document_id: UUID) -> bytes | None:
        sql = """
            SELECT ds.pdf_blob
            FROM bi_documents bd
            JOIN document_snapshots ds ON ds.id = bd.latest_snapshot_id
            WHERE bd.document_id = %(document_id)s
              AND ds.pdf_blob IS NOT NULL
            LIMIT 1
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"document_id": document_id})
                row = cur.fetchone()
        if row is None:
            return None
        return bytes(row[0])

    def search(self, query: str, limit: int) -> dict[str, list[dict[str, Any]]]:
        start = time.perf_counter()
        normalized = query.strip().lower()
        if len(normalized) < 3:
            logger.info(
                "presentation.search_repo_fetch query_length=%s limit=%s document_rows=0 location_rows=0 reduced_location_rows=0 total_ms=%.2f",
                len(normalized),
                limit,
                (time.perf_counter() - start) * 1000.0,
            )
            return {"documents": [], "locations": []}

        canonical_exact = normalized
        canonical_prefix = f"{normalized}%"
        canonical_contains = f"%{normalized}%"
        numeric_only = normalized if normalized.isdigit() else None
        numeric_prefix = f"{numeric_only}%" if numeric_only is not None else None

        document_sql = """
            WITH top_location AS (
                SELECT
                    bdl.document_id,
                    bl.normalized_location AS location_display,
                    ROW_NUMBER() OVER (
                        PARTITION BY bdl.document_id
                        ORDER BY bdl.mention_count DESC, bl.normalized_location ASC, bl.location_id ASC
                    ) AS rn
                FROM bi_document_locations bdl
                JOIN bi_locations bl ON bl.location_id = bdl.location_id
            ),
            document_matches AS (
                SELECT
                    bd.document_id,
                    COALESCE(bd.canonical_number, '') AS scp_number,
                    COALESCE(LOWER(bd.canonical_number), '') AS canonical_scp_id,
                    bd.url AS scp_url,
                    tl.location_display,
                    CASE
                        WHEN bd.latest_snapshot_id IS NOT NULL THEN '/api/map/document/' || bd.document_id || '/pdf'
                        ELSE NULL
                    END AS pdf_url,
                    CASE
                        WHEN LOWER(bd.canonical_number) = %(canonical_exact)s THEN 0
                        WHEN %(numeric_only)s::text IS NOT NULL
                            AND REPLACE(LOWER(bd.canonical_number), 'scp-', '') = %(numeric_only)s::text THEN 1
                        WHEN LOWER(bd.canonical_number) LIKE %(canonical_prefix)s THEN 2
                        WHEN %(numeric_prefix)s::text IS NOT NULL
                            AND REPLACE(LOWER(bd.canonical_number), 'scp-', '') LIKE %(numeric_prefix)s::text THEN 3
                        WHEN LOWER(bd.canonical_number) LIKE %(canonical_contains)s THEN 4
                        WHEN LOWER(COALESCE(tl.location_display, '')) LIKE %(canonical_prefix)s THEN 5
                        WHEN LOWER(COALESCE(tl.location_display, '')) LIKE %(canonical_contains)s THEN 6
                        ELSE 9
                    END AS rank_bucket
                FROM bi_documents bd
                LEFT JOIN top_location tl ON tl.document_id = bd.document_id AND tl.rn = 1
                WHERE
                    LOWER(bd.canonical_number) = %(canonical_exact)s
                    OR LOWER(bd.canonical_number) LIKE %(canonical_prefix)s
                    OR LOWER(bd.canonical_number) LIKE %(canonical_contains)s
                    OR LOWER(COALESCE(tl.location_display, '')) LIKE %(canonical_prefix)s
                    OR LOWER(COALESCE(tl.location_display, '')) LIKE %(canonical_contains)s
                    OR (
                        %(numeric_only)s::text IS NOT NULL
                        AND REPLACE(LOWER(bd.canonical_number), 'scp-', '') = %(numeric_only)s::text
                    )
                    OR (
                        %(numeric_prefix)s::text IS NOT NULL
                        AND REPLACE(LOWER(bd.canonical_number), 'scp-', '') LIKE %(numeric_prefix)s::text
                    )
            )
            SELECT DISTINCT
                dm.document_id,
                dm.scp_number,
                dm.canonical_scp_id,
                dm.scp_url,
                dm.location_display,
                dm.pdf_url,
                dm.rank_bucket
            FROM document_matches dm
            ORDER BY
                dm.rank_bucket ASC,
                dm.scp_number ASC,
                dm.scp_url ASC,
                dm.document_id ASC
            LIMIT %(limit)s
        """

        location_sql = """
            WITH location_matches AS (
                SELECT
                    bl.location_id,
                    bl.normalized_location AS name,
                    bl.latitude,
                    bl.longitude,
                    bl.precision,
                    bl.location_rank,
                    bl.document_count,
                    bl.parent_location_id,
                    CASE
                        WHEN LOWER(bl.normalized_location) = %(canonical_exact)s THEN 0
                        WHEN LOWER(COALESCE(bl.city, '')) = %(canonical_exact)s THEN 1
                        WHEN LOWER(COALESCE(bl.region, '')) = %(canonical_exact)s THEN 2
                        WHEN LOWER(COALESCE(bl.country, '')) = %(canonical_exact)s THEN 3
                        WHEN LOWER(bl.normalized_location) LIKE %(canonical_prefix)s THEN 4
                        WHEN LOWER(bl.normalized_location) LIKE %(canonical_contains)s THEN 5
                        WHEN LOWER(COALESCE(bl.city, '')) LIKE %(canonical_contains)s THEN 6
                        WHEN LOWER(COALESCE(bl.region, '')) LIKE %(canonical_contains)s THEN 7
                        WHEN LOWER(COALESCE(bl.country, '')) LIKE %(canonical_contains)s THEN 8
                        ELSE 9
                    END AS rank_bucket
                FROM bi_locations bl
                WHERE
                    LOWER(bl.normalized_location) LIKE %(canonical_contains)s
                    OR LOWER(COALESCE(bl.city, '')) LIKE %(canonical_contains)s
                    OR LOWER(COALESCE(bl.region, '')) LIKE %(canonical_contains)s
                    OR LOWER(COALESCE(bl.country, '')) LIKE %(canonical_contains)s
            )
            SELECT
                lm.location_id,
                lm.name,
                lm.latitude,
                lm.longitude,
                lm.precision,
                lm.location_rank,
                lm.document_count,
                lm.parent_location_id
            FROM location_matches lm
            WHERE
                lm.latitude IS NOT NULL
                AND lm.longitude IS NOT NULL
                AND lm.latitude = lm.latitude
                AND lm.longitude = lm.longitude
                AND lm.latitude BETWEEN -90 AND 90
                AND lm.longitude BETWEEN -180 AND 180
            ORDER BY
                lm.rank_bucket ASC,
                lm.document_count DESC,
                lm.name ASC,
                lm.location_id ASC
            LIMIT %(limit)s
        """

        params = {
            "canonical_exact": canonical_exact,
            "canonical_prefix": canonical_prefix,
            "canonical_contains": canonical_contains,
            "numeric_only": numeric_only,
            "numeric_prefix": numeric_prefix,
            "limit": limit,
        }
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(document_sql, params)
                doc_columns = [d[0] for d in cur.description]
                doc_rows = [dict(zip(doc_columns, row, strict=True)) for row in cur.fetchall()]
                location_params = dict(params)
                location_params["limit"] = min(limit * 5, 50)
                cur.execute(location_sql, location_params)
                loc_columns = [d[0] for d in cur.description]
                loc_rows = [dict(zip(loc_columns, row, strict=True)) for row in cur.fetchall()]

        for row in doc_rows:
            row.pop("rank_bucket", None)
        deduped_locations = self._reduce_semantic_city_rows(loc_rows)
        logger.info(
            "presentation.search_repo_fetch query_length=%s limit=%s document_rows=%s location_rows=%s reduced_location_rows=%s total_ms=%.2f",
            len(normalized),
            limit,
            len(doc_rows),
            len(loc_rows),
            len(deduped_locations),
            (time.perf_counter() - start) * 1000.0,
        )
        return {"documents": doc_rows, "locations": deduped_locations[:limit]}
