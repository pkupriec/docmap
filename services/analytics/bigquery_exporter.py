from __future__ import annotations

import os
import logging
import time
from typing import Any
from typing import Callable

from services.common.db import get_connection

PRIMARY_KEYS: dict[str, list[str]] = {
    "bi_documents": ["document_id"],
    "bi_locations": ["location_id"],
    "bi_document_locations": ["document_id", "location_id"],
}
logger = logging.getLogger(__name__)

ExportTableCallback = Callable[[str, str, str | None], None]


def export_all_bi_tables(
    mode: str = "full",
    *,
    on_table: ExportTableCallback | None = None,
) -> None:
    logger.info("analytics.bigquery_export_all_start mode=%s", mode)
    for table_name in ("bi_documents", "bi_locations", "bi_document_locations"):
        if on_table:
            on_table(table_name, "started", None)
        try:
            export_table_to_bigquery(table_name, mode=mode)
            if on_table:
                on_table(table_name, "succeeded", None)
        except Exception as exc:
            if on_table:
                on_table(table_name, "failed", str(exc))
            raise
    logger.info("analytics.bigquery_export_all_done mode=%s", mode)


def export_table_to_bigquery(table_name: str, *, mode: str = "full") -> None:
    logger.info("analytics.bigquery_export_start table=%s mode=%s", table_name, mode)
    max_retries = 2
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            _export_table_to_bigquery_once(table_name, mode=mode)
            return
        except Exception as exc:
            last_error = exc
            if attempt == max_retries:
                break
            backoff_seconds = 2 ** (attempt - 1)
            logger.warning(
                "analytics.bigquery_export_retry table=%s mode=%s attempt=%s backoff_seconds=%s reason=%s",
                table_name,
                mode,
                attempt,
                backoff_seconds,
                type(exc).__name__,
            )
            time.sleep(backoff_seconds)

    logger.error("analytics.bigquery_export_failed table=%s mode=%s", table_name, mode)
    raise RuntimeError(f"BigQuery export failed for table: {table_name}") from last_error


def _export_table_to_bigquery_once(table_name: str, *, mode: str) -> None:
    client = get_bigquery_client()
    project_id = _required_env("GCP_PROJECT_ID")
    dataset = os.getenv("BIGQUERY_DATASET", "docmap_mvp")
    location = os.getenv("BIGQUERY_LOCATION", "US")
    rows = _fetch_postgres_rows(table_name)
    table_id = f"{project_id}.{dataset}.{table_name}"
    _ensure_dataset(client, project_id, dataset, location)

    if mode == "full":
        _load_rows(client, table_id, rows, write_disposition="WRITE_TRUNCATE", location=location)
        logger.info("analytics.bigquery_export_done table=%s mode=%s rows=%s", table_name, mode, len(rows))
        return

    if mode != "incremental":
        raise ValueError(f"Unsupported export mode: {mode}")

    staging_table = f"{project_id}.{dataset}.{table_name}__staging"
    _load_rows(client, staging_table, rows, write_disposition="WRITE_TRUNCATE", location=location)
    _ensure_target_table(client, table_id, staging_table)
    _merge_from_staging(client, table_id, staging_table, table_name, location=location)
    logger.info("analytics.bigquery_export_done table=%s mode=%s rows=%s", table_name, mode, len(rows))


def get_bigquery_client():
    from google.cloud import bigquery

    return bigquery.Client(project=_required_env("GCP_PROJECT_ID"))


def _fetch_postgres_rows(table_name: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table_name}")  # table_name controlled internally
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _ensure_dataset(client, project_id: str, dataset: str, location: str) -> None:
    dataset_id = f"{project_id}.{dataset}"
    try:
        client.get_dataset(dataset_id)
    except Exception:
        from google.cloud import bigquery

        ds = bigquery.Dataset(dataset_id)
        ds.location = location
        client.create_dataset(ds, exists_ok=True)


def _load_rows(client, table_id: str, rows: list[dict[str, Any]], *, write_disposition: str, location: str) -> None:
    from google.cloud import bigquery

    job_config = bigquery.LoadJobConfig(
        autodetect=True,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=write_disposition,
    )
    load_job = client.load_table_from_json(rows, table_id, job_config=job_config, location=location)
    load_job.result()


def _ensure_target_table(client, target_table: str, staging_table: str) -> None:
    sql = (
        f"CREATE TABLE IF NOT EXISTS `{target_table}` "
        f"AS SELECT * FROM `{staging_table}` WHERE 1=0"
    )
    client.query(sql).result()


def _merge_from_staging(client, target_table: str, staging_table: str, table_name: str, *, location: str) -> None:
    keys = PRIMARY_KEYS[table_name]
    sample_rows = _fetch_postgres_rows(table_name)
    columns = list(sample_rows[0].keys()) if sample_rows else keys
    update_columns = [c for c in columns if c not in keys]

    on_clause = " AND ".join([f"T.{k} = S.{k}" for k in keys])
    update_clause = ", ".join([f"{c} = S.{c}" for c in update_columns]) or "T.updated_at = T.updated_at"
    insert_columns = ", ".join(columns)
    insert_values = ", ".join([f"S.{c}" for c in columns])

    sql = f"""
    MERGE `{target_table}` T
    USING `{staging_table}` S
    ON {on_clause}
    WHEN MATCHED THEN
      UPDATE SET {update_clause}
    WHEN NOT MATCHED THEN
      INSERT ({insert_columns}) VALUES ({insert_values})
    """
    client.query(sql, location=location).result()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
