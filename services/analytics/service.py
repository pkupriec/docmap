from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Callable

from psycopg import Connection

from services.common.db import get_connection
from services.analytics.geometry_assets import build_admin_boundaries_asset
from services.analytics.scripts.build_admin_boundaries_source import build_source_dataset

logger = logging.getLogger(__name__)
_ADMIN_LEVEL_RE = re.compile(r"^admin_level_(\d+)$")

AnalyticsStepCallback = Callable[[str, int], None]

ANALYTICS_STEP_NAMES = [
    "bi_documents",
    "bi_locations",
    "bi_document_locations",
    "admin_boundaries_source",
    "admin_boundaries",
    "bi_location_hierarchy",
]


def build_admin_boundaries_source(_conn: Connection) -> int:
    source_path = Path(
        os.getenv(
            "DOCMAP_ADMIN_BOUNDARIES_SOURCE",
            str(Path(__file__).resolve().parent / "assets" / "admin_boundaries_source.geojson"),
        )
    )
    stats = build_source_dataset(source_path)
    return int(stats.get("total_features", 0))


def build_bi_documents(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_documents")
        cur.execute(
            """
            INSERT INTO bi_documents
                (
                    document_id,
                    scp_object_id,
                    canonical_number,
                    url,
                    title,
                    preview_text,
                    latest_snapshot_id,
                    latest_snapshot_at,
                    location_count
                )
            SELECT
                d.id AS document_id,
                d.scp_object_id,
                so.canonical_number,
                d.url,
                d.title,
                CASE
                    WHEN latest.clean_text IS NULL THEN NULL
                    ELSE SUBSTRING(latest.clean_text FROM 1 FOR 300)
                END AS preview_text,
                latest.id AS latest_snapshot_id,
                latest.created_at AS latest_snapshot_at,
                COALESCE(loc.location_count, 0) AS location_count
            FROM documents d
            LEFT JOIN scp_objects so ON so.id = d.scp_object_id
            LEFT JOIN LATERAL (
                SELECT ds.id, ds.created_at, ds.clean_text
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
    def _parse_bbox(value):
        if not isinstance(value, list) or len(value) != 4:
            return None
        try:
            south, north, west, east = [float(item) for item in value]
        except (TypeError, ValueError):
            return None
        return (south, north, west, east)

    def _bbox_contains_point(bbox, lat, lon):
        if bbox is None or lat is None or lon is None:
            return False
        south, north, west, east = bbox
        return south <= lat <= north and west <= lon <= east

    def _admin_level(rank: str) -> int | None:
        match = _ADMIN_LEVEL_RE.match(rank or "")
        if match is None:
            return None
        return int(match.group(1))

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_locations")
        cur.execute(
            """
            SELECT
                gl.id,
                gl.normalized_location,
                gl.country,
                gl.region,
                gl.city,
                gl.latitude,
                gl.longitude,
                gl.precision,
                COALESCE(NULLIF(gl.location_rank, ''), 'unknown') AS location_rank,
                gl.osm_boundingbox,
                COALESCE(docs.document_count, 0) AS document_count
            FROM geo_locations gl
            LEFT JOIN (
                SELECT location_id, COUNT(DISTINCT document_id) AS document_count
                FROM document_locations
                GROUP BY location_id
            ) docs ON docs.location_id = gl.id
            ORDER BY gl.id ASC
            """
        )
        rows = cur.fetchall()

        nodes: list[dict[str, object]] = []
        for row in rows:
            rank_raw = str(row[8] or "unknown").strip().lower()
            if rank_raw == "region":
                rank_raw = "admin_region"
            bbox = _parse_bbox(row[9])
            node = {
                "location_id": row[0],
                "normalized_location": row[1],
                "country": row[2],
                "region": row[3],
                "city": row[4],
                "latitude": row[5],
                "longitude": row[6],
                "precision": row[7],
                "location_rank": rank_raw,
                "bbox": bbox,
                "document_count": int(row[10] or 0),
            }
            nodes.append(node)

        by_country: dict[str, list[dict[str, object]]] = {}
        by_id: dict[object, dict[str, object]] = {}
        for node in nodes:
            by_id[node["location_id"]] = node
            country = str(node.get("country") or "").strip().lower()
            by_country.setdefault(country, []).append(node)

        def _parent_for(node: dict[str, object]) -> object | None:
            rank = str(node.get("location_rank") or "unknown")
            country = str(node.get("country") or "").strip().lower()
            lat = node.get("latitude")
            lon = node.get("longitude")
            group = by_country.get(country, [])
            if rank == "city":
                admin_candidates = [
                    item
                    for item in group
                    if (
                        str(item.get("location_rank") or "").startswith("admin_level_")
                        or str(item.get("location_rank") or "") == "admin_region"
                    )
                    and item.get("location_id") != node.get("location_id")
                    and _bbox_contains_point(item.get("bbox"), lat, lon)
                ]
                admin_candidates.sort(
                    key=lambda item: (
                        -int(_admin_level(str(item.get("location_rank"))) or 0),
                        str(item.get("location_id")),
                    )
                )
                if admin_candidates:
                    return admin_candidates[0].get("location_id")

            level = _admin_level(rank)
            if level is not None:
                parent_admin = [
                    item
                    for item in group
                    if item.get("location_id") != node.get("location_id")
                    and _admin_level(str(item.get("location_rank") or "")) is not None
                    and int(_admin_level(str(item.get("location_rank") or "")) or 0) < level
                    and _bbox_contains_point(item.get("bbox"), lat, lon)
                ]
                parent_admin.sort(
                    key=lambda item: (
                        -int(_admin_level(str(item.get("location_rank") or "")) or 0),
                        str(item.get("location_id")),
                    )
                )
                if parent_admin:
                    return parent_admin[0].get("location_id")

            country_candidates = [
                item
                for item in group
                if item.get("location_id") != node.get("location_id")
                and str(item.get("location_rank") or "") == "country"
            ]
            if country_candidates:
                country_candidates.sort(key=lambda item: str(item.get("location_id")))
                return country_candidates[0].get("location_id")
            return None

        insert_rows = []
        for node in nodes:
            insert_rows.append(
                (
                    node["location_id"],
                    node["normalized_location"],
                    node["country"],
                    node["region"],
                    node["city"],
                    node["latitude"],
                    node["longitude"],
                    node["precision"],
                    node["location_rank"],
                    _parent_for(node),
                    node["document_count"],
                )
            )

        if insert_rows:
            cur.executemany(
                """
                INSERT INTO bi_locations
                    (
                        location_id,
                        normalized_location,
                        country,
                        region,
                        city,
                        latitude,
                        longitude,
                        precision,
                        location_rank,
                        parent_location_id,
                        document_count
                    )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                insert_rows,
            )
            return len(insert_rows)
        return 0


def build_bi_document_locations(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_document_locations")
        cur.execute(
            """
            WITH RECURSIVE mention_rows AS (
                SELECT
                    dl.id AS document_location_id,
                    dl.document_id,
                    dl.location_id,
                    lm.evidence_quote
                FROM document_locations dl
                LEFT JOIN location_mentions lm ON lm.id = dl.mention_id
            ),
            expanded AS (
                SELECT
                    mr.document_location_id,
                    mr.document_id,
                    mr.location_id,
                    mr.evidence_quote,
                    0 AS depth
                FROM mention_rows mr

                UNION ALL

                SELECT
                    e.document_location_id,
                    e.document_id,
                    parent.parent_location_id AS location_id,
                    e.evidence_quote,
                    e.depth + 1 AS depth
                FROM expanded e
                JOIN bi_locations parent ON parent.location_id = e.location_id
                WHERE
                    parent.parent_location_id IS NOT NULL
                    AND parent.parent_location_id <> e.location_id
                    AND e.depth < 32
            ),
            rolled AS (
                SELECT DISTINCT
                    e.document_location_id,
                    e.document_id,
                    e.location_id,
                    e.evidence_quote
                FROM expanded e
            )
            INSERT INTO bi_document_locations
                (document_id, location_id, mention_count, evidence_quote)
            SELECT
                r.document_id,
                r.location_id,
                COUNT(*) AS mention_count,
                MIN(
                    CASE
                        WHEN r.evidence_quote IS NULL OR r.evidence_quote = '' THEN NULL
                        ELSE r.evidence_quote
                    END
                ) AS evidence_quote
            FROM rolled r
            GROUP BY r.document_id, r.location_id
            """
        )
        return cur.rowcount


def build_bi_location_hierarchy(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_location_hierarchy")
        cur.execute(
            """
            WITH RECURSIVE chain AS (
                SELECT
                    bl.location_id AS descendant_location_id,
                    bl.location_id AS ancestor_location_id,
                    0 AS depth
                FROM bi_locations bl

                UNION ALL

                SELECT
                    c.descendant_location_id,
                    parent.parent_location_id AS ancestor_location_id,
                    c.depth + 1 AS depth
                FROM chain c
                JOIN bi_locations parent ON parent.location_id = c.ancestor_location_id
                WHERE
                    parent.parent_location_id IS NOT NULL
                    AND parent.parent_location_id <> c.descendant_location_id
                    AND c.depth < 64
            ),
            dedup AS (
                SELECT
                    ancestor_location_id,
                    descendant_location_id,
                    MIN(depth) AS depth
                FROM chain
                GROUP BY ancestor_location_id, descendant_location_id
            ),
            continent_country AS (
                SELECT DISTINCT
                    continent.location_id AS ancestor_location_id,
                    country.location_id AS country_location_id,
                    1 AS depth
                FROM bi_locations continent
                JOIN bi_admin_boundaries bab
                    ON bab.location_id = continent.location_id
                    AND bab.location_rank = 'continent'
                JOIN bi_locations country
                    ON COALESCE(NULLIF(LOWER(country.location_rank), ''), 'unknown') = 'country'
                    AND country.latitude IS NOT NULL
                    AND country.longitude IS NOT NULL
                    AND country.latitude = country.latitude
                    AND country.longitude = country.longitude
                WHERE
                    ST_Intersects(
                        ST_SetSRID(ST_MakePoint(country.longitude, country.latitude), 4326),
                        ST_SetSRID(ST_GeomFromGeoJSON((bab.feature_json -> 'geometry')::text), 4326)
                    )
            ),
            continent_expanded AS (
                SELECT
                    cc.ancestor_location_id,
                    cc.country_location_id AS descendant_location_id,
                    cc.depth
                FROM continent_country cc

                UNION ALL

                SELECT
                    ce.ancestor_location_id,
                    d.descendant_location_id,
                    ce.depth + d.depth AS depth
                FROM continent_country ce
                JOIN dedup d ON d.ancestor_location_id = ce.country_location_id
            ),
            boundary_nodes AS (
                SELECT
                    bab.location_id,
                    COALESCE(NULLIF(LOWER(bl.location_rank), ''), 'unknown') AS location_rank,
                    ST_SetSRID(ST_GeomFromGeoJSON((bab.feature_json -> 'geometry')::text), 4326) AS geom
                FROM bi_admin_boundaries bab
                JOIN bi_locations bl ON bl.location_id = bab.location_id
            ),
            spatial_admin_seed AS (
                SELECT DISTINCT
                    ancestor.location_id AS ancestor_location_id,
                    descendant.location_id AS descendant_location_id,
                    1 AS depth
                FROM boundary_nodes ancestor
                JOIN boundary_nodes descendant
                    ON descendant.location_id <> ancestor.location_id
                    AND (
                        descendant.location_rank = 'country'
                        OR descendant.location_rank = 'admin_region'
                        OR descendant.location_rank LIKE 'admin_level_%'
                    )
                WHERE
                    ST_Intersects(ancestor.geom, descendant.geom)
                    AND ST_Area(ST_Intersection(ancestor.geom, descendant.geom)) > 0
            ),
            spatial_admin_expanded AS (
                SELECT
                    sas.ancestor_location_id,
                    sas.descendant_location_id,
                    sas.depth
                FROM spatial_admin_seed sas

                UNION ALL

                SELECT
                    sae.ancestor_location_id,
                    d.descendant_location_id,
                    sae.depth + d.depth AS depth
                FROM spatial_admin_seed sae
                JOIN dedup d ON d.ancestor_location_id = sae.descendant_location_id
            ),
            all_links AS (
                SELECT
                    d.ancestor_location_id,
                    d.descendant_location_id,
                    d.depth
                FROM dedup d

                UNION ALL

                SELECT
                    ce.ancestor_location_id,
                    ce.descendant_location_id,
                    ce.depth
                FROM continent_expanded ce

                UNION ALL

                SELECT
                    sae.ancestor_location_id,
                    sae.descendant_location_id,
                    sae.depth
                FROM spatial_admin_expanded sae
            ),
            all_dedup AS (
                SELECT
                    ancestor_location_id,
                    descendant_location_id,
                    MIN(depth) AS depth
                FROM all_links
                GROUP BY ancestor_location_id, descendant_location_id
            )
            INSERT INTO bi_location_hierarchy
                (ancestor_location_id, descendant_location_id, depth)
            SELECT
                d.ancestor_location_id,
                d.descendant_location_id,
                d.depth
            FROM all_dedup d
            """
        )
        return cur.rowcount


def rebuild_analytics(*, on_step: AnalyticsStepCallback | None = None, start_index: int = 0) -> dict[str, int]:
    logger.info("analytics.rebuild_start")
    steps = [
        ("bi_documents", build_bi_documents),
        ("bi_locations", build_bi_locations),
        ("bi_document_locations", build_bi_document_locations),
        ("admin_boundaries_source", build_admin_boundaries_source),
        ("admin_boundaries", lambda conn: build_admin_boundaries_asset(conn).features_written),
        ("bi_location_hierarchy", build_bi_location_hierarchy),
    ]
    if start_index < 0:
        start_index = 0
    if start_index > len(steps):
        start_index = len(steps)

    documents_rows = 0
    locations_rows = 0
    links_rows = 0
    hierarchy_rows = 0
    admin_boundaries_source_rows = 0
    admin_boundaries_rows = 0
    with get_connection() as conn:
        for idx, (name, fn) in enumerate(steps):
            if idx < start_index:
                continue
            rows = fn(conn)
            if name == "bi_documents":
                documents_rows = rows
            elif name == "bi_locations":
                locations_rows = rows
            elif name == "bi_document_locations":
                links_rows = rows
            elif name == "bi_location_hierarchy":
                hierarchy_rows = rows
            elif name == "admin_boundaries_source":
                admin_boundaries_source_rows = rows
            else:
                admin_boundaries_rows = rows
            if on_step:
                on_step(name, rows)
        conn.commit()

    stats = {
        "bi_documents": documents_rows,
        "bi_locations": locations_rows,
        "bi_document_locations": links_rows,
        "bi_location_hierarchy": hierarchy_rows,
        "admin_boundaries_source": admin_boundaries_source_rows,
        "admin_boundaries": admin_boundaries_rows,
    }
    logger.info("analytics.rebuild_done stats=%s", stats)
    return stats
