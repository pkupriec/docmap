from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from services.common.db import get_connection


@dataclass(frozen=True)
class ResolvedLocation:
    location_id: str
    depth: int


class PresentationRepository:
    def list_locations(self) -> list[dict[str, Any]]:
        sql = """
            SELECT
                bl.location_id,
                bl.normalized_location AS name,
                bl.latitude,
                bl.longitude,
                bl.precision,
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
            WITH candidates AS (
                SELECT
                    %(location_id)s AS location_id,
                    0 AS depth

                UNION

                SELECT
                    h.ancestor_location_id,
                    h.depth
                FROM bi_location_hierarchy h
                WHERE h.descendant_location_id = %(location_id)s
            ),
            depth_with_docs AS (
                SELECT MIN(c.depth) AS depth
                FROM candidates c
                JOIN bi_document_locations bdl ON bdl.location_id = c.location_id
            )
            SELECT
                c.location_id,
                c.depth
            FROM candidates c
            JOIN depth_with_docs d ON d.depth = c.depth
            ORDER BY c.location_id ASC
            LIMIT 1
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"location_id": location_id})
                row = cur.fetchone()
        if row is None:
            return None
        return ResolvedLocation(location_id=str(row[0]), depth=int(row[1]))

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

    def list_location_documents(self, location_id: Any) -> list[dict[str, Any]]:
        sql = """
            SELECT
                bd.document_id,
                COALESCE(bd.canonical_number, '') AS scp_number,
                COALESCE(LOWER(bd.canonical_number), '') AS canonical_scp_id,
                bd.url AS scp_url,
                CASE
                    WHEN bd.latest_snapshot_id IS NOT NULL THEN '/api/map/document/' || bd.document_id || '/pdf'
                    ELSE NULL
                END AS pdf_url
            FROM bi_document_locations bdl
            JOIN bi_documents bd ON bd.document_id = bdl.document_id
            WHERE bdl.location_id = %(location_id)s
            ORDER BY
                CASE WHEN bd.canonical_number IS NULL THEN 1 ELSE 0 END ASC,
                bd.canonical_number ASC,
                bd.url ASC,
                bd.document_id ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"location_id": location_id})
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def list_document_locations(self, document_id: Any) -> list[dict[str, Any]]:
        sql = """
            SELECT
                bdl.document_id,
                bl.location_id,
                bl.normalized_location AS name,
                bl.latitude,
                bl.longitude,
                bl.precision,
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
