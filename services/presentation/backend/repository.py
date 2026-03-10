from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
            WHERE bl.latitude IS NOT NULL AND bl.longitude IS NOT NULL
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

    def list_location_documents(self, location_id: Any) -> list[dict[str, Any]]:
        sql = """
            SELECT
                bd.document_id,
                bd.scp_object_id,
                bd.title,
                bd.url,
                bd.preview_text,
                bdl.evidence_quote,
                bdl.mention_count
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
            WHERE bl.latitude IS NOT NULL AND bl.longitude IS NOT NULL
            ORDER BY bl.document_count DESC, bl.location_id ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
        return [dict(zip(columns, row, strict=True)) for row in rows]
