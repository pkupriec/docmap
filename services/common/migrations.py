from __future__ import annotations

import logging
import os
from pathlib import Path

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


def run_startup_migrations() -> None:
    """Development migration strategy: reset and recreate schema on startup.

    Controlled by env var `DB_RESET_ON_START`.
    Values treated as true: 1, true, yes, on.
    """

    flag = os.getenv("DB_RESET_ON_START", "1").strip().lower()
    should_reset = flag in {"1", "true", "yes", "on"}
    if not should_reset:
        logger.info("db.migrations.skip_reset_on_start")
        return

    root = Path(__file__).resolve().parents[2]
    sql_paths = [root / rel for rel in SQL_FILES]

    logger.warning("db.migrations.reset_start mode=drop_tables_recreate")
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DROP VIEW IF EXISTS v_active_pipeline_runs;")
                cur.execute("DROP FUNCTION IF EXISTS prune_pipeline_logs_keep_last_10_runs();")
                for table_name in TABLE_DROP_ORDER:
                    cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
                for sql_path in sql_paths:
                    logger.info("db.migrations.apply path=%s", sql_path)
                    cur.execute(_read_sql(sql_path))
            conn.commit()
    logger.warning("db.migrations.reset_done")
