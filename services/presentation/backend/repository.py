from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from typing import Any
from uuid import UUID

from services.common.db import get_connection

logger = logging.getLogger(__name__)

RankFilter = Literal["default", "all"]
GeometryDetail = Literal["low", "full"]
DEFAULT_BOUNDARY_RANKS: set[str] = {"city", "admin_region", "region", "country", "continent", "ocean"}


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


class PresentationRepository:
    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _low_detail_artifact_paths(self) -> list[Path]:
        configured = os.getenv("DOCMAP_BOUNDARIES_LOW_ARTIFACT_PATH")
        if configured:
            return [Path(configured)]
        root = self._project_root()
        return [
            root / "services" / "presentation" / "frontend" / "src" / "assets" / "admin_boundaries.geojson",
            Path("/app/services/presentation/frontend/src/assets/admin_boundaries.geojson"),
            Path("/app/services/analytics/assets/admin_boundaries.low.default.v1.geojson"),
        ]

    def _normalize_rank(self, rank: object | None) -> str:
        value = str(rank or "unknown").strip().lower()
        if value == "region":
            return "admin_region"
        return value or "unknown"

    def _geometry_supported(self, geometry: object) -> bool:
        if not isinstance(geometry, dict):
            return False
        return geometry.get("type") in {"Polygon", "MultiPolygon"}

    def _simplify_ring(self, ring: list[list[float]], stride: int) -> list[list[float]]:
        if stride <= 1 or len(ring) <= 4:
            return ring
        is_closed = ring[0] == ring[-1]
        core = ring[:-1] if is_closed else ring
        if len(core) <= 3:
            return ring
        reduced = [core[0]]
        for idx in range(1, len(core) - 1):
            if idx % stride == 0:
                reduced.append(core[idx])
        reduced.append(core[-1])
        if len(reduced) < 3:
            reduced = core[:]
        if is_closed:
            if reduced[0] != reduced[-1]:
                reduced.append(reduced[0])
            if len(reduced) < 4:
                reduced = core[:] + [core[0]]
        return reduced

    def _simplify_geometry(self, geometry: dict[str, Any], *, rank: str) -> dict[str, Any]:
        stride_by_rank: dict[str, int] = {
            "city": 2,
            "admin_region": 4,
            "country": 8,
            "continent": 12,
            "ocean": 12,
        }
        stride = stride_by_rank.get(rank, 6)
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        if geometry_type == "Polygon" and isinstance(coordinates, list):
            return {
                "type": "Polygon",
                "coordinates": [
                    self._simplify_ring(ring, stride) if isinstance(ring, list) else ring
                    for ring in coordinates
                ],
            }
        if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
            simplified_polygons: list[list[list[list[float]]]] = []
            for polygon in coordinates:
                if not isinstance(polygon, list):
                    continue
                simplified_polygons.append(
                    [self._simplify_ring(ring, stride) if isinstance(ring, list) else ring for ring in polygon]
                )
            return {
                "type": "MultiPolygon",
                "coordinates": simplified_polygons,
            }
        return geometry

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
        geometry_detail: GeometryDetail,
    ) -> dict[str, Any] | None:
        geometry = parsed.get("geometry")
        if not isinstance(geometry, dict):
            return None
        raw_properties = parsed.get("properties")
        properties = raw_properties if isinstance(raw_properties, dict) else {}
        rank = self._normalize_rank(properties.get("location_rank"))
        output_geometry = (
            self._simplify_geometry(geometry, rank=rank) if geometry_detail == "low" else geometry
        )
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
                    "type": output_geometry.get("type"),
                    "coordinates": output_geometry.get("coordinates"),
                },
            }
        return {
            "type": "Feature",
            "properties": properties,
            "geometry": {
                "type": output_geometry.get("type"),
                "coordinates": output_geometry.get("coordinates"),
            },
        }

    def _rank_allowed(self, rank: str, rank_filter: RankFilter) -> bool:
        if rank_filter == "all":
            return True
        return rank in DEFAULT_BOUNDARY_RANKS

    def _load_low_detail_default_artifact(self, *, minimal: bool) -> dict[str, Any] | None:
        for candidate in self._low_detail_artifact_paths():
            if not candidate.exists() or not candidate.is_file():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            features_payload = payload.get("features")
            if not isinstance(features_payload, list):
                continue
            artifact_start = time.perf_counter()
            features: list[dict[str, Any]] = []
            for feature in features_payload:
                if not isinstance(feature, dict):
                    continue
                properties = feature.get("properties")
                if not isinstance(properties, dict):
                    continue
                rank = self._normalize_rank(properties.get("location_rank"))
                if not self._rank_allowed(rank, "default"):
                    continue
                serialized = self._serialize_feature(feature, minimal=minimal, geometry_detail="low")
                if serialized is None:
                    continue
                features.append(serialized)
            logger.info(
                "presentation.boundaries_artifact_loaded path=%s minimal=%s features=%s duration_ms=%.2f",
                candidate,
                minimal,
                len(features),
                (time.perf_counter() - artifact_start) * 1000.0,
            )
            return {
                "type": "FeatureCollection",
                "features": features,
            }
        return None

    def get_admin_boundaries_geojson(
        self,
        *,
        minimal: bool = False,
        rank_filter: RankFilter = "default",
        geometry_detail: GeometryDetail = "full",
    ) -> dict[str, Any]:
        if rank_filter == "default" and geometry_detail == "low":
            artifact = self._load_low_detail_default_artifact(minimal=minimal)
            if artifact is not None:
                return artifact

        total_start = time.perf_counter()
        sql = """
            SELECT feature_json
            FROM bi_admin_boundaries
            ORDER BY
                CASE location_rank
                    WHEN 'city' THEN 0
                    WHEN 'country' THEN 0
                    WHEN 'admin_region' THEN 1
                    WHEN 'continent' THEN 2
                    WHEN 'ocean' THEN 3
                    ELSE 9
                END,
                location_id ASC
        """
        db_start = time.perf_counter()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        db_elapsed_ms = (time.perf_counter() - db_start) * 1000.0
        transform_start = time.perf_counter()
        features: list[dict[str, Any]] = []
        for row in rows:
            parsed = self._parse_feature_row(row[0] if row else None)
            if parsed is None:
                continue
            properties = parsed.get("properties")
            if not isinstance(properties, dict):
                continue
            rank = self._normalize_rank(properties.get("location_rank"))
            if not self._rank_allowed(rank, rank_filter):
                continue
            serialized = self._serialize_feature(
                parsed,
                minimal=minimal,
                geometry_detail=geometry_detail,
            )
            if serialized is None:
                continue
            features.append(serialized)
        total_elapsed_ms = (time.perf_counter() - total_start) * 1000.0
        transform_elapsed_ms = (time.perf_counter() - transform_start) * 1000.0
        logger.info(
            "presentation.boundaries_repo_fetch minimal=%s rank_filter=%s geometry_detail=%s rows=%s features=%s db_ms=%.2f transform_ms=%.2f total_ms=%.2f",
            minimal,
            rank_filter,
            geometry_detail,
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
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def resolve_location_for_documents(self, location_id: Any) -> ResolvedLocation | None:
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
            return None
        return ResolvedLocation(location_id=str(row[0]), depth=int(row[1]), location_rank=str(row[2]))

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
    ) -> ScopedLocationDocuments:
        scope_rank_normalized = str(scope_rank).lower()
        if scope_rank_normalized == "region":
            scope_rank_normalized = "admin_region"

        if scope_rank_normalized == "city":
            rank_filter = ("city",)
        else:
            rank_filter = ()

        rank_filter_sql = ", ".join(["%s"] * len(rank_filter)) if rank_filter else ""
        params: list[Any] = [location_id, *rank_filter]
        rank_clause = (
            f"AND COALESCE(NULLIF(LOWER(bl.location_rank), ''), 'unknown') IN ({rank_filter_sql})"
            if rank_filter
            else ""
        )

        scope_sql = f"""
            WITH scope_locations AS (
                SELECT
                    h.descendant_location_id AS location_id
                FROM bi_location_hierarchy h
                JOIN bi_locations bl ON bl.location_id = h.descendant_location_id
                WHERE
                    h.ancestor_location_id = %s
                    {rank_clause}
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
                cur.execute(scope_sql, [*params, limit, offset])
                columns = [d[0] for d in cur.description]
                rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]

                cur.execute(
                    f"""
                    WITH scope_locations AS (
                        SELECT
                            h.descendant_location_id AS location_id
                        FROM bi_location_hierarchy h
                        JOIN bi_locations bl ON bl.location_id = h.descendant_location_id
                        WHERE
                            h.ancestor_location_id = %s
                            {rank_clause}
                    )
                    SELECT COUNT(DISTINCT sl.location_id) AS location_count
                    FROM scope_locations sl
                    """,
                    [location_id, *rank_filter],
                )
                scope_row = cur.fetchone()
                location_count = int(scope_row[0]) if scope_row is not None and scope_row[0] is not None else 0

                cur.execute(
                    f"""
                    WITH scope_locations AS (
                        SELECT
                            h.descendant_location_id AS location_id
                        FROM bi_location_hierarchy h
                        JOIN bi_locations bl ON bl.location_id = h.descendant_location_id
                        WHERE
                            h.ancestor_location_id = %s
                            {rank_clause}
                    ),
                    scoped_docs AS (
                        SELECT DISTINCT bdl.document_id
                        FROM bi_document_locations bdl
                        JOIN scope_locations sl ON sl.location_id = bdl.location_id
                    )
                    SELECT COUNT(*) AS total_items
                    FROM scoped_docs
                    """,
                    [location_id, *rank_filter],
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
        return ScopedLocationDocuments(
            scope_rank=scope_rank_normalized,
            location_count=location_count,
            total_items=total_items,
            items=items,
        )

    def list_document_locations(self, document_id: Any) -> list[dict[str, Any]]:
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
        return [dict(zip(columns, row, strict=True)) for row in rows]

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
        normalized = query.strip().lower()
        if len(normalized) < 3:
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
                cur.execute(location_sql, params)
                loc_columns = [d[0] for d in cur.description]
                loc_rows = [dict(zip(loc_columns, row, strict=True)) for row in cur.fetchall()]

        for row in doc_rows:
            row.pop("rank_bucket", None)
        return {"documents": doc_rows, "locations": loc_rows}
