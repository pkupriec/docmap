from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import psycopg

from services.common.db import get_connection


logger = logging.getLogger(__name__)


SQL_FILES = (
    Path("database/schema.sql"),
    Path("database/control_plane.sql"),
    Path("database/seed_scp_objects.sql"),
)

TABLE_DROP_ORDER = (
    # Control plane
    "pipeline_commands",
    "pipeline_logs",
    "pipeline_progress",
    "pipeline_stage_runs",
    "pipeline_runs",
    # BI
    "bi_document_locations",
    "bi_admin_boundaries",
    "bi_locations",
    "bi_documents",
    # Operational
    "document_locations",
    "geo_location_aliases",
    "geo_locations",
    "location_mentions",
    "extraction_runs",
    "document_snapshots",
    "documents",
    "scp_objects",
)


def _read_sql(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def _wait_for_db_ready(max_wait_seconds: int = 30, interval_seconds: float = 1.0) -> None:
    deadline = time.time() + max_wait_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with get_connection():
                return
        except psycopg.OperationalError as exc:
            last_error = exc
            logger.warning("db.migrations.waiting_for_db_ready retry_in_seconds=%.1f", interval_seconds)
            time.sleep(interval_seconds)
    if last_error is not None:
        raise last_error


def _iter_geometry_positions(geometry: object):
    if not isinstance(geometry, dict):
        return
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        for ring in coordinates:
            if not isinstance(ring, list):
                continue
            for point in ring:
                if (
                    isinstance(point, list)
                    and len(point) >= 2
                    and isinstance(point[0], (int, float))
                    and isinstance(point[1], (int, float))
                ):
                    yield float(point[0]), float(point[1])
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        for polygon in coordinates:
            if not isinstance(polygon, list):
                continue
            for ring in polygon:
                if not isinstance(ring, list):
                    continue
                for point in ring:
                    if (
                        isinstance(point, list)
                        and len(point) >= 2
                        and isinstance(point[0], (int, float))
                        and isinstance(point[1], (int, float))
                    ):
                        yield float(point[0]), float(point[1])


def _feature_bounds_from_payload(payload: object) -> tuple[float, float, float, float] | None:
    if isinstance(payload, dict):
        parsed = payload
    elif isinstance(payload, (str, bytes, bytearray)):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
    else:
        return None
    if not isinstance(parsed, dict):
        return None
    positions = list(_iter_geometry_positions(parsed.get("geometry")))
    if not positions:
        return None
    longitudes = [lon for lon, _ in positions]
    latitudes = [lat for _, lat in positions]
    return (min(longitudes), min(latitudes), max(longitudes), max(latitudes))


def _backfill_boundary_envelopes() -> None:
    with get_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT location_id::text, feature_json
                FROM bi_admin_boundaries
                WHERE
                    min_lon IS NULL
                    OR min_lat IS NULL
                    OR max_lon IS NULL
                    OR max_lat IS NULL
                ORDER BY location_id ASC
                """
            )
            rows = cur.fetchall()
            updates: list[tuple[float, float, float, float, str]] = []
            for location_id, payload in rows:
                bounds = _feature_bounds_from_payload(payload)
                if bounds is None:
                    continue
                updates.append((*bounds, str(location_id)))
            if updates:
                cur.executemany(
                    """
                    UPDATE bi_admin_boundaries
                    SET
                        min_lon = %s,
                        min_lat = %s,
                        max_lon = %s,
                        max_lat = %s
                    WHERE location_id = %s::uuid
                    """,
                    updates,
                )


def _apply_runtime_schema_patches() -> None:
    """Apply lightweight idempotent schema patches needed by runtime code."""
    with get_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                ALTER TABLE IF EXISTS pipeline_commands
                ADD COLUMN IF NOT EXISTS claim_token UUID
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS pipeline_commands
                ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS pipeline_commands
                ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pipeline_commands_claimable
                ON pipeline_commands(status, lease_expires_at, id ASC)
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS document_snapshots
                ADD COLUMN IF NOT EXISTS pdf_blob BYTEA
                """
            )
            # Indexes added after initial bootstrap to improve extractor/geocoder
            # lookup patterns and enforce one-run-per-snapshot assumptions.
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_snapshots_document_created_desc
                ON document_snapshots(document_id, created_at DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_snapshots_created_at_id
                ON document_snapshots(created_at, id)
                """
            )
            cur.execute("DROP INDEX IF EXISTS idx_extraction_runs_snapshot")
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_extraction_runs_snapshot_id
                ON extraction_runs(snapshot_id)
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_document_locations_mention_id
                ON document_locations(mention_id)
                WHERE mention_id IS NOT NULL
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS bi_documents
                ADD COLUMN IF NOT EXISTS preview_text TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS bi_locations
                ADD COLUMN IF NOT EXISTS parent_location_id UUID
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS bi_locations
                ADD COLUMN IF NOT EXISTS location_rank TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS bi_document_locations
                ADD COLUMN IF NOT EXISTS evidence_quote TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS location_rank TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS osm_type TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS osm_id BIGINT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS osm_category TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS osm_place_type TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS osm_addresstype TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS osm_admin_level INTEGER
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS osm_place_rank INTEGER
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS osm_boundingbox JSONB
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS boundary_intent BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS geocode_candidates JSONB
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS canonical_id TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS canonical_resolution_method TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS canonical_confidence SMALLINT
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS canonical_resolution_details JSONB
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS geo_locations
                ADD COLUMN IF NOT EXISTS identity_key TEXT
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_geo_locations_identity_key
                ON geo_locations(identity_key)
                WHERE identity_key IS NOT NULL
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS geo_location_aliases (
                    normalized_location TEXT PRIMARY KEY,
                    location_id UUID NOT NULL REFERENCES geo_locations(id) ON DELETE CASCADE,
                    created_at TIMESTAMP NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_geo_location_aliases_location_id
                ON geo_location_aliases(location_id)
                """
            )
            cur.execute(
                """
                INSERT INTO geo_location_aliases (normalized_location, location_id)
                SELECT normalized_location, id
                FROM geo_locations
                ON CONFLICT (normalized_location) DO NOTHING
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_geo_locations_osm_identity
                ON geo_locations(osm_type, osm_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_geo_locations_canonical_id
                ON geo_locations(canonical_id)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS geo_canonical_places (
                    canonical_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    place_type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    parent_canonical_id TEXT REFERENCES geo_canonical_places(canonical_id),
                    country_canonical_id TEXT REFERENCES geo_canonical_places(canonical_id),
                    centroid_lat DOUBLE PRECISION,
                    centroid_lon DOUBLE PRECISION,
                    valid_from TIMESTAMP,
                    valid_to TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_geo_canonical_places_source_source_id
                ON geo_canonical_places(source, source_id)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS geo_canonical_aliases (
                    canonical_id TEXT NOT NULL REFERENCES geo_canonical_places(canonical_id) ON DELETE CASCADE,
                    alias TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL,
                    alias_type TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    PRIMARY KEY (canonical_id, normalized_alias, alias_type)
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_geo_canonical_aliases_normalized_alias_type
                ON geo_canonical_aliases(normalized_alias, alias_type)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS geo_canonical_concordances (
                    canonical_id TEXT NOT NULL REFERENCES geo_canonical_places(canonical_id) ON DELETE CASCADE,
                    external_source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    PRIMARY KEY (external_source, external_id)
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_geo_canonical_concordances_canonical
                ON geo_canonical_concordances(canonical_id)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bi_location_hierarchy (
                    ancestor_location_id UUID NOT NULL REFERENCES geo_locations(id),
                    descendant_location_id UUID NOT NULL REFERENCES geo_locations(id),
                    depth INTEGER NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    PRIMARY KEY (ancestor_location_id, descendant_location_id)
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS document_snapshots
                ADD COLUMN IF NOT EXISTS pdf_thumbnail_webp BYTEA
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bi_location_hierarchy_descendant_depth
                ON bi_location_hierarchy(descendant_location_id, depth)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bi_location_hierarchy_ancestor_depth
                ON bi_location_hierarchy(ancestor_location_id, depth)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bi_document_locations_location_document
                ON bi_document_locations(location_id, document_id)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bi_admin_boundaries (
                    location_id UUID PRIMARY KEY REFERENCES geo_locations(id),
                    location_rank TEXT NOT NULL,
                    feature_json JSONB NOT NULL,
                    min_lon DOUBLE PRECISION,
                    min_lat DOUBLE PRECISION,
                    max_lon DOUBLE PRECISION,
                    max_lat DOUBLE PRECISION,
                    updated_at TIMESTAMP NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS bi_admin_boundaries
                ADD COLUMN IF NOT EXISTS min_lon DOUBLE PRECISION
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS bi_admin_boundaries
                ADD COLUMN IF NOT EXISTS min_lat DOUBLE PRECISION
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS bi_admin_boundaries
                ADD COLUMN IF NOT EXISTS max_lon DOUBLE PRECISION
                """
            )
            cur.execute(
                """
                ALTER TABLE IF EXISTS bi_admin_boundaries
                ADD COLUMN IF NOT EXISTS max_lat DOUBLE PRECISION
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bi_admin_boundaries_rank
                ON bi_admin_boundaries(location_rank)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bi_admin_boundaries_lat_bounds
                ON bi_admin_boundaries(min_lat, max_lat)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bi_admin_boundaries_lon_bounds
                ON bi_admin_boundaries(min_lon, max_lon)
                """
            )
    _backfill_boundary_envelopes()


def run_startup_migrations() -> None:
    """Optional startup schema reset for development.

    Controlled by env var `DB_RESET_ON_START`.
    Values treated as true: 1, true, yes, on.
    """

    _wait_for_db_ready(
        max_wait_seconds=int(os.getenv("DB_STARTUP_MAX_WAIT_SECONDS", "30")),
        interval_seconds=float(os.getenv("DB_STARTUP_RETRY_INTERVAL_SECONDS", "1")),
    )

    flag = os.getenv("DB_RESET_ON_START", "0").strip().lower()
    should_reset = flag in {"1", "true", "yes", "on"}
    if not should_reset:
        _apply_runtime_schema_patches()
        logger.info("db.migrations.skip_reset_on_start")
        return

    root = Path(__file__).resolve().parents[2]
    sql_paths = [root / rel for rel in SQL_FILES]

    drop_flag = os.getenv("DB_DROP_TABLES_ON_START", "0").strip().lower()
    should_drop = drop_flag in {"1", "true", "yes", "on"}

    mode = "drop_tables_recreate" if should_drop else "apply_only"
    logger.warning("db.migrations.reset_start mode=%s", mode)
    with get_connection() as conn:
        # SQL files may contain explicit BEGIN/COMMIT blocks, so run startup
        # migrations with autocommit enabled to avoid nested-transaction warnings.
        conn.autocommit = True
        with conn.cursor() as cur:
            if should_drop:
                cur.execute("DROP VIEW IF EXISTS v_active_pipeline_runs;")
                cur.execute("DROP FUNCTION IF EXISTS prune_pipeline_logs_keep_last_10_runs();")
                for table_name in TABLE_DROP_ORDER:
                    cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
            else:
                cur.execute("SELECT to_regclass('public.scp_objects')")
                schema_exists = cur.fetchone()[0] is not None
                if schema_exists:
                    logger.info("db.migrations.apply_skip reason=schema_exists mode=apply_only")
            if should_drop or not schema_exists:
                for sql_path in sql_paths:
                    logger.info("db.migrations.apply path=%s", sql_path)
                    cur.execute(_read_sql(sql_path))
    _apply_runtime_schema_patches()
    logger.warning("db.migrations.reset_done")
