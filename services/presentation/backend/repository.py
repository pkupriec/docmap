from __future__ import annotations

import logging
import math
import re
import time
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID

from psycopg import Connection

from services.common.db import get_connection
from services.presentation.backend.boundaries_repository import BoundariesRepository

logger = logging.getLogger(__name__)
_WHITESPACE_RE = re.compile(r"\s+")
ConnectionProvider = Callable[[], AbstractContextManager[Connection]]


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
class LocationDocumentsResult:
    resolved: ResolvedLocation | None
    location_display: str | None
    scoped: ScopedLocationDocuments | None


class PresentationRepository(BoundariesRepository):
    def __init__(self, connection_provider: ConnectionProvider | None = None) -> None:
        super().__init__(connection_provider or get_connection)

    def _normalize_text(self, value: object | None) -> str:
        return _WHITESPACE_RE.sub(" ", str(value or "").strip().lower())

    def _normalize_rank(self, rank: object | None) -> str:
        value = str(rank or "unknown").strip().lower()
        if value == "region":
            return "admin_region"
        return value or "unknown"

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
        with self._connect() as conn:
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
        with self._connect() as conn:
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

    def get_location_documents(
        self,
        location_id: Any,
        *,
        limit: int,
        offset: int,
    ) -> LocationDocumentsResult:
        """Resolve a location and fetch its page using one checked-out connection."""
        with self._connect() as conn:
            repo = PresentationRepository(lambda: nullcontext(conn))
            resolved = repo.resolve_location_for_documents(location_id)
            if resolved is None:
                return LocationDocumentsResult(resolved=None, location_display=None, scoped=None)
            resolved_uuid = UUID(resolved.location_id)
            semantic_ids = repo.get_semantic_scope_location_ids(
                resolved_uuid,
                scope_rank=resolved.location_rank,
            )
            scoped = repo.list_location_documents(
                resolved_uuid,
                scope_rank=resolved.location_rank,
                limit=limit,
                offset=offset,
                semantic_scope_location_ids=semantic_ids,
            )
            return LocationDocumentsResult(
                resolved=resolved,
                location_display=repo.get_location_name(resolved_uuid),
                scoped=scoped,
            )

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
        with self._connect() as conn:
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
        with self._connect() as conn:
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
        with self._connect() as conn:
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
                CASE
                    WHEN ds.pdf_thumbnail_webp IS NOT NULL THEN '/api/map/document/' || bd.document_id || '/thumbnail'
                    ELSE NULL
                END AS thumbnail_url,
                dc.total_items,
                sc.location_count
            FROM page_docs pd
            JOIN bi_documents bd ON bd.document_id = pd.document_id
            LEFT JOIN document_snapshots ds ON ds.id = bd.latest_snapshot_id
            CROSS JOIN doc_counts dc
            CROSS JOIN scope_counts sc
            ORDER BY
                CASE WHEN bd.canonical_number IS NULL THEN 1 ELSE 0 END ASC,
                bd.canonical_number ASC,
                bd.url ASC,
                bd.document_id ASC
        """
        with self._connect() as conn:
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
                "thumbnail_url": row["thumbnail_url"],
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
        with self._connect() as conn:
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
        with self._connect() as conn:
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
                END AS pdf_url,
                CASE
                    WHEN ds.pdf_thumbnail_webp IS NOT NULL THEN '/api/map/document/' || bd.document_id || '/thumbnail'
                    ELSE NULL
                END AS thumbnail_url
            FROM bi_documents bd
            LEFT JOIN document_snapshots ds ON ds.id = bd.latest_snapshot_id
            LEFT JOIN top_location tl
                ON tl.document_id = bd.document_id
                AND tl.rn = 1
            WHERE bd.document_id = %(document_id)s
            LIMIT 1
        """
        with self._connect() as conn:
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
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"document_id": document_id})
                row = cur.fetchone()
        if row is None:
            return None
        return bytes(row[0])

    def get_document_thumbnail(self, document_id: UUID) -> bytes | None:
        sql = """
            SELECT ds.pdf_thumbnail_webp
            FROM bi_documents bd
            JOIN document_snapshots ds ON ds.id = bd.latest_snapshot_id
            WHERE bd.document_id = %(document_id)s
              AND ds.pdf_thumbnail_webp IS NOT NULL
            LIMIT 1
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"document_id": document_id})
                row = cur.fetchone()
        return bytes(row[0]) if row is not None else None

    def get_document_pdf_size(self, document_id: UUID) -> int | None:
        sql = """
            SELECT OCTET_LENGTH(ds.pdf_blob)
            FROM bi_documents bd
            JOIN document_snapshots ds ON ds.id = bd.latest_snapshot_id
            WHERE bd.document_id = %(document_id)s
              AND ds.pdf_blob IS NOT NULL
            LIMIT 1
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"document_id": document_id})
                row = cur.fetchone()
        return int(row[0]) if row is not None else None

    def get_document_pdf_range(self, document_id: UUID, *, start: int, length: int) -> bytes | None:
        """Read only the requested bytea slice; PostgreSQL need not send the full PDF."""
        sql = """
            SELECT SUBSTRING(ds.pdf_blob FROM %(sql_start)s FOR %(length)s)
            FROM bi_documents bd
            JOIN document_snapshots ds ON ds.id = bd.latest_snapshot_id
            WHERE bd.document_id = %(document_id)s
              AND ds.pdf_blob IS NOT NULL
            LIMIT 1
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    {"document_id": document_id, "sql_start": start + 1, "length": length},
                )
                row = cur.fetchone()
        return bytes(row[0]) if row is not None else None

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
                        WHEN ds.pdf_thumbnail_webp IS NOT NULL THEN '/api/map/document/' || bd.document_id || '/thumbnail'
                        ELSE NULL
                    END AS thumbnail_url,
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
                LEFT JOIN document_snapshots ds ON ds.id = bd.latest_snapshot_id
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
                dm.thumbnail_url,
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
        with self._connect() as conn:
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
