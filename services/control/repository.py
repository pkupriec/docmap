from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from services.common.db import get_connection
from services.control.constants import STAGE_ORDER, STAGES_BY_PIPELINE_TYPE, downstream_stages


class DuplicatePendingCommandError(Exception):
    pass


class NotFoundError(Exception):
    pass


class ControlRepository:
    def _connect(self) -> psycopg.Connection:
        return get_connection()

    def enqueue_command(
        self,
        command_type: str,
        pipeline_run_id: int | None = None,
        stage_name: str | None = None,
        payload_json: dict[str, Any] | None = None,
        requested_by: str | None = None,
        dedupe_key: str | None = None,
    ) -> int:
        payload = payload_json or {}
        with self._connect() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO pipeline_commands
                            (command_type, pipeline_run_id, stage_name, payload_json, requested_by, dedupe_key)
                        VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                        RETURNING id
                        """,
                        (
                            command_type,
                            pipeline_run_id,
                            stage_name,
                            json.dumps(payload),
                            requested_by,
                            dedupe_key,
                        ),
                    )
                except psycopg.errors.UniqueViolation as exc:
                    raise DuplicatePendingCommandError() from exc
                command_id = cur.fetchone()[0]
            conn.commit()
        return int(command_id)

    def get_command(self, command_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM pipeline_commands WHERE id = %s", (command_id,))
                return cur.fetchone()

    def poll_next_command(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.transaction():
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT *
                        FROM pipeline_commands
                        WHERE status IN ('pending', 'accepted')
                        ORDER BY id ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                        """
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    if row["status"] == "pending":
                        cur.execute(
                            "UPDATE pipeline_commands SET status = 'accepted' WHERE id = %s",
                            (row["id"],),
                        )
                        row["status"] = "accepted"
                    return row

    def complete_command(self, command_id: int, status: str, error_message: str | None = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pipeline_commands
                    SET status = %s,
                        processed_at = NOW(),
                        error_message = %s
                    WHERE id = %s
                    """,
                    (status, error_message, command_id),
                )
            conn.commit()

    def defer_command(self, command_id: int, payload_json: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pipeline_commands
                    SET status = 'accepted', payload_json = %s::jsonb
                    WHERE id = %s
                    """,
                    (json.dumps(payload_json), command_id),
                )
            conn.commit()

    def find_active_run(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM pipeline_runs
                    WHERE status IN ('pending', 'running', 'cancelling')
                    ORDER BY id ASC
                    LIMIT 1
                    """
                )
                return cur.fetchone()

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM pipeline_runs WHERE id = %s", (run_id,))
                return cur.fetchone()

    def list_runs(self, limit: int, status: str | None, pipeline_type: str | None) -> list[dict[str, Any]]:
        query = "SELECT * FROM pipeline_runs"
        filters: list[str] = []
        params: list[Any] = []
        if status:
            filters.append("status = %s")
            params.append(status)
        if pipeline_type:
            filters.append("pipeline_type = %s")
            params.append(pipeline_type)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY id DESC LIMIT %s"
        params.append(limit)

        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(params))
                return list(cur.fetchall())

    def create_run(
        self,
        pipeline_type: str,
        target_scope: str,
        parameters_json: dict[str, Any],
        requested_by: str | None = None,
        replacement_for_run_id: int | None = None,
        created_by_command_id: int | None = None,
    ) -> int:
        stages = STAGES_BY_PIPELINE_TYPE[pipeline_type]
        with self._connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO pipeline_runs
                            (pipeline_type, status, target_scope, parameters_json, requested_by,
                             replacement_for_run_id, created_by_command_id)
                        VALUES (%s, 'pending', %s, %s::jsonb, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            pipeline_type,
                            target_scope,
                            json.dumps(parameters_json),
                            requested_by,
                            replacement_for_run_id,
                            created_by_command_id,
                        ),
                    )
                    run_id = int(cur.fetchone()[0])
                    for stage in stages:
                        cur.execute(
                            """
                            INSERT INTO pipeline_stage_runs
                                (pipeline_run_id, stage_name, status, stage_order)
                            VALUES (%s, %s, 'pending', %s)
                            """,
                            (run_id, stage, STAGE_ORDER[stage]),
                        )
            conn.commit()
        return run_id

    def set_run_status(
        self,
        run_id: int,
        status: str,
        *,
        current_stage_name: str | None = None,
        error_message: str | None = None,
        clear_finished: bool = False,
    ) -> None:
        set_finished = status in ("cancelled", "failed", "success")
        with self._connect() as conn:
            with conn.cursor() as cur:
                if clear_finished:
                    cur.execute(
                        """
                        UPDATE pipeline_runs
                        SET status = %s,
                            current_stage_name = %s,
                            started_at = NULL,
                            finished_at = NULL,
                            error_message = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (status, current_stage_name, error_message, run_id),
                    )
                elif set_finished:
                    cur.execute(
                        """
                        UPDATE pipeline_runs
                        SET status = %s,
                            current_stage_name = %s,
                            finished_at = NOW(),
                            error_message = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (status, current_stage_name, error_message, run_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE pipeline_runs
                        SET status = %s,
                            current_stage_name = %s,
                            started_at = CASE WHEN started_at IS NULL AND %s = 'running' THEN NOW() ELSE started_at END,
                            error_message = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (status, current_stage_name, status, error_message, run_id),
                    )
            conn.commit()

    def list_stages(self, run_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM pipeline_stage_runs
                    WHERE pipeline_run_id = %s
                    ORDER BY stage_order ASC
                    """,
                    (run_id,),
                )
                return list(cur.fetchall())

    def set_stage_status(
        self,
        run_id: int,
        stage_name: str,
        status: str,
        *,
        items_total: int | None = None,
        items_completed: int | None = None,
        items_failed: int | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pipeline_stage_runs
                    SET status = %s,
                        items_total = COALESCE(%s, items_total),
                        items_completed = COALESCE(%s, items_completed),
                        items_failed = COALESCE(%s, items_failed),
                        started_at = CASE WHEN started_at IS NULL AND %s = 'running' THEN NOW() ELSE started_at END,
                        finished_at = CASE WHEN %s IN ('success', 'failed', 'skipped') THEN NOW() ELSE NULL END,
                        error_message = %s,
                        updated_at = NOW()
                    WHERE pipeline_run_id = %s AND stage_name = %s
                    """,
                    (
                        status,
                        items_total,
                        items_completed,
                        items_failed,
                        status,
                        status,
                        error_message,
                        run_id,
                        stage_name,
                    ),
                )
            conn.commit()

    def reset_stages_from(self, run_id: int, stage_name: str) -> None:
        names = downstream_stages(stage_name)
        with self._connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE pipeline_stage_runs
                        SET status = 'pending',
                            items_total = NULL,
                            items_completed = 0,
                            items_failed = 0,
                            started_at = NULL,
                            finished_at = NULL,
                            error_message = NULL,
                            updated_at = NOW()
                        WHERE pipeline_run_id = %s AND stage_name = ANY(%s)
                        """,
                        (run_id, names),
                    )
                    cur.execute(
                        "DELETE FROM pipeline_progress WHERE pipeline_run_id = %s AND stage_name = ANY(%s)",
                        (run_id, names),
                    )
            conn.commit()

    def upsert_progress(
        self,
        run_id: int,
        stage_name: str,
        *,
        current_index: int,
        total_items: int | None,
        items_completed: int,
        items_failed: int,
        current_document_id: int | None = None,
        current_document_url: str | None = None,
        current_item_label: str | None = None,
        message: str | None = None,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_progress (
                        pipeline_run_id, stage_name, current_index, total_items, items_completed,
                        items_failed, current_document_id, current_document_url, current_item_label,
                        message, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (pipeline_run_id, stage_name)
                    DO UPDATE SET
                        current_index = EXCLUDED.current_index,
                        total_items = EXCLUDED.total_items,
                        items_completed = EXCLUDED.items_completed,
                        items_failed = EXCLUDED.items_failed,
                        current_document_id = EXCLUDED.current_document_id,
                        current_document_url = EXCLUDED.current_document_url,
                        current_item_label = EXCLUDED.current_item_label,
                        message = EXCLUDED.message,
                        updated_at = NOW()
                    """,
                    (
                        run_id,
                        stage_name,
                        current_index,
                        total_items,
                        items_completed,
                        items_failed,
                        current_document_id,
                        current_document_url,
                        current_item_label,
                        message,
                    ),
                )
            conn.commit()

    def list_progress(self, run_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM pipeline_progress
                    WHERE pipeline_run_id = %s
                    ORDER BY stage_name ASC
                    """,
                    (run_id,),
                )
                return list(cur.fetchall())

    def append_log(
        self,
        run_id: int,
        stage_name: str | None,
        service_name: str,
        level: str,
        message: str,
        *,
        event_type: str | None = None,
        document_id: int | None = None,
        document_url: str | None = None,
        current_index: int | None = None,
        payload_json: dict[str, Any] | None = None,
    ) -> int:
        payload = payload_json or None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_logs (
                        pipeline_run_id, stage_name, service_name, level, event_type, message,
                        document_id, document_url, current_index, payload_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        run_id,
                        stage_name,
                        service_name,
                        level,
                        event_type,
                        message,
                        document_id,
                        document_url,
                        current_index,
                        json.dumps(payload) if payload is not None else None,
                    ),
                )
                log_id = int(cur.fetchone()[0])
            conn.commit()
        return log_id

    def prune_logs_keep_last_10_runs(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT prune_pipeline_logs_keep_last_10_runs()")
                count = int(cur.fetchone()[0])
            conn.commit()
        return count

    def list_logs(
        self,
        run_id: int,
        *,
        after_id: int | None = None,
        limit: int = 200,
        level: str | None = None,
        stage_name: str | None = None,
        service_name: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM pipeline_logs WHERE pipeline_run_id = %s"
        params: list[Any] = [run_id]
        if after_id is not None:
            query += " AND id > %s"
            params.append(after_id)
        if level:
            query += " AND level = %s"
            params.append(level)
        if stage_name:
            query += " AND stage_name = %s"
            params.append(stage_name)
        if service_name:
            query += " AND service_name = %s"
            params.append(service_name)
        query += " ORDER BY id ASC LIMIT %s"
        params.append(limit)
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(params))
                return list(cur.fetchall())

    def update_command_payload(self, command_id: int, payload_json: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE pipeline_commands SET payload_json = %s::jsonb WHERE id = %s",
                    (json.dumps(payload_json), command_id),
                )
            conn.commit()

    def mark_active_run_cancelling(self, run_id: int) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pipeline_runs
                    SET status = 'cancelling', updated_at = NOW()
                    WHERE id = %s AND status IN ('pending', 'running', 'cancelling')
                    """,
                    (run_id,),
                )
            conn.commit()

    def any_active_run(self) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM pipeline_runs WHERE status IN ('pending', 'running', 'cancelling'))"
                )
                return bool(cur.fetchone()[0])

    def run_exists(self, run_id: int) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT EXISTS (SELECT 1 FROM pipeline_runs WHERE id = %s)", (run_id,))
                return bool(cur.fetchone()[0])

    def stage_exists(self, run_id: int, stage_name: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM pipeline_stage_runs WHERE pipeline_run_id = %s AND stage_name = %s)",
                    (run_id, stage_name),
                )
                return bool(cur.fetchone()[0])

    def get_latest_state_snapshot(self, run_id: int, after_log_id: int = 0) -> dict[str, Any]:
        run = self.get_run(run_id)
        if not run:
            raise NotFoundError(f"run {run_id} not found")
        stages = self.list_stages(run_id)
        progress = self.list_progress(run_id)
        logs = self.list_logs(run_id, after_id=after_log_id, limit=500)
        return {
            "run": run,
            "stages": stages,
            "progress": progress,
            "logs": logs,
            "server_time": datetime.now(timezone.utc),
        }
