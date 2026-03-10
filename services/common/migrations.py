from __future__ import annotations

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
    "bi_locations",
    "bi_documents",
    # Operational
    "document_locations",
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


def _apply_runtime_schema_patches() -> None:
    """Apply lightweight idempotent schema patches needed by runtime code."""
    with get_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
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


def run_startup_migrations() -> None:
    """Optional startup schema reset for development.

    Controlled by env var `DB_RESET_ON_START`.
    Values treated as true: 1, true, yes, on.
    """

    _wait_for_db_ready(
        max_wait_seconds=int(os.getenv("DB_STARTUP_MAX_WAIT_SECONDS", "30")),
        interval_seconds=float(os.getenv("DB_STARTUP_RETRY_INTERVAL_SECONDS", "1")),
    )
    _apply_runtime_schema_patches()

    flag = os.getenv("DB_RESET_ON_START", "0").strip().lower()
    should_reset = flag in {"1", "true", "yes", "on"}
    if not should_reset:
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
                    logger.warning("db.migrations.reset_done")
                    return
            for sql_path in sql_paths:
                logger.info("db.migrations.apply path=%s", sql_path)
                cur.execute(_read_sql(sql_path))
    logger.warning("db.migrations.reset_done")
