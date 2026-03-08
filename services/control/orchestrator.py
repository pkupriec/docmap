from __future__ import annotations

import logging
import threading
import time
from typing import Any

from services.analytics import rebuild_analytics
from services.analytics.bigquery_exporter import export_all_bi_tables
from services.control.constants import STAGES_BY_PIPELINE_TYPE, downstream_stages
from services.control.repository import ControlRepository
from services.crawler import generate_scp_urls, process_documents
from services.extractor import process_pending_snapshots
from services.geocoder import normalize_pending_mentions, process_pending_mentions


logger = logging.getLogger(__name__)
TEST_CRAWL_LIMIT = 20


class ControlOrchestrator:
    def __init__(self, repository: ControlRepository | None = None, poll_interval_seconds: float = 1.0) -> None:
        self.repository = repository or ControlRepository()
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self.run_forever, name="control-orchestrator", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("control.orchestrator.tick_failed")
            time.sleep(self.poll_interval_seconds)

    def tick(self) -> None:
        command = self.repository.poll_next_command()
        if command:
            self._apply_command(command)

        active = self.repository.find_active_run()
        if not active:
            return

        if active["status"] == "pending":
            self._execute_run(active["id"])
            return
        if active["status"] == "cancelling":
            current_stage = active.get("current_stage_name")
            if current_stage:
                self.repository.set_stage_status(
                    active["id"],
                    current_stage,
                    "skipped",
                    error_message="cancelled",
                )
            self.repository.set_run_status(active["id"], "cancelled", current_stage_name=None)
            self.repository.append_log(
                active["id"],
                current_stage,
                "pipeline",
                "INFO",
                "Run cancelled",
                event_type="run_status",
            )

    def _apply_command(self, command: dict[str, Any]) -> None:
        command_type = command["command_type"]
        payload = dict(command.get("payload_json") or {})

        try:
            if command_type == "start_run":
                self._apply_start(command, payload)
            elif command_type == "cancel_run":
                self._apply_cancel(command)
            elif command_type == "retry_run":
                self._apply_retry_run(command, payload)
            elif command_type == "retry_stage":
                self._apply_retry_stage(command, payload)
            else:
                self.repository.complete_command(command["id"], "rejected", f"unsupported command {command_type}")
        except Exception as exc:
            self.repository.complete_command(command["id"], "failed", str(exc))
            logger.exception("control.orchestrator.command_failed command_id=%s", command["id"])

    def _apply_start(self, command: dict[str, Any], payload: dict[str, Any]) -> None:
        active = self.repository.find_active_run()
        is_deferred = bool(payload.get("deferred"))

        if active and not is_deferred:
            self.repository.mark_active_run_cancelling(active["id"])
            payload["deferred"] = True
            self.repository.defer_command(command["id"], payload)
            return

        if active and is_deferred:
            return

        run_id = self.repository.create_run(
            pipeline_type=payload["pipeline_type"],
            target_scope=payload["target_scope"],
            parameters_json=payload,
            requested_by=command.get("requested_by"),
            replacement_for_run_id=payload.get("replacement_for_run_id"),
            created_by_command_id=command["id"],
        )
        self.repository.append_log(
            run_id,
            None,
            "pipeline",
            "INFO",
            "Run created from start command",
            event_type="run_status",
        )
        self.repository.complete_command(command["id"], "applied")

    def _apply_cancel(self, command: dict[str, Any]) -> None:
        run_id = command.get("pipeline_run_id")
        if not run_id or not self.repository.run_exists(run_id):
            self.repository.complete_command(command["id"], "rejected", "run not found")
            return

        run = self.repository.get_run(run_id)
        if run["status"] in ("cancelled", "failed", "success"):
            self.repository.complete_command(command["id"], "rejected", "run is already terminal")
            return

        self.repository.mark_active_run_cancelling(run_id)
        self.repository.append_log(run_id, None, "pipeline", "INFO", "Cancellation requested", event_type="run_status")
        self.repository.complete_command(command["id"], "applied")

    def _apply_retry_run(self, command: dict[str, Any], payload: dict[str, Any]) -> None:
        target_run_id = command.get("pipeline_run_id")
        if not target_run_id:
            self.repository.complete_command(command["id"], "rejected", "missing pipeline_run_id")
            return

        target = self.repository.get_run(target_run_id)
        if not target:
            self.repository.complete_command(command["id"], "rejected", "run not found")
            return

        active = self.repository.find_active_run()
        is_deferred = bool(payload.get("deferred"))
        if active and not is_deferred:
            self.repository.mark_active_run_cancelling(active["id"])
            payload["deferred"] = True
            self.repository.defer_command(command["id"], payload)
            return
        if active and is_deferred:
            return

        new_payload = {
            "pipeline_type": target["pipeline_type"],
            "target_scope": target["target_scope"],
            **(target.get("parameters_json") or {}),
            **(payload.get("options") or {}),
            "replacement_for_run_id": target_run_id,
        }

        run_id = self.repository.create_run(
            pipeline_type=target["pipeline_type"],
            target_scope=target["target_scope"],
            parameters_json=new_payload,
            requested_by=command.get("requested_by"),
            replacement_for_run_id=target_run_id,
            created_by_command_id=command["id"],
        )
        self.repository.append_log(run_id, None, "pipeline", "INFO", f"Run created as retry of {target_run_id}", event_type="run_status")
        self.repository.complete_command(command["id"], "applied")

    def _apply_retry_stage(self, command: dict[str, Any], payload: dict[str, Any]) -> None:
        run_id = command.get("pipeline_run_id")
        stage_name = command.get("stage_name")
        if not run_id or not stage_name:
            self.repository.complete_command(command["id"], "rejected", "run_id and stage_name required")
            return

        if not self.repository.stage_exists(run_id, stage_name):
            self.repository.complete_command(command["id"], "rejected", "run or stage not found")
            return

        active = self.repository.find_active_run()
        is_deferred = bool(payload.get("deferred"))
        if active and not is_deferred:
            self.repository.mark_active_run_cancelling(active["id"])
            payload["deferred"] = True
            self.repository.defer_command(command["id"], payload)
            return
        if active and is_deferred:
            return

        self.repository.reset_stages_from(run_id, stage_name)
        self.repository.set_run_status(run_id, "pending", current_stage_name=None, error_message=None, clear_finished=True)
        self.repository.append_log(
            run_id,
            stage_name,
            "pipeline",
            "INFO",
            f"Stage retry requested from {stage_name}; downstream stages reset",
            event_type="stage_status",
            payload_json={"stages_reset": downstream_stages(stage_name)},
        )
        self.repository.complete_command(command["id"], "applied")

    def _execute_run(self, run_id: int) -> None:
        run = self.repository.get_run(run_id)
        if not run:
            return

        stages = STAGES_BY_PIPELINE_TYPE[run["pipeline_type"]]
        self.repository.set_run_status(run_id, "running", current_stage_name=stages[0])
        self.repository.append_log(run_id, None, "pipeline", "INFO", "Run started", event_type="run_status")

        try:
            for stage in stages:
                self.repository.set_run_status(run_id, "running", current_stage_name=stage)
                self.repository.set_stage_status(run_id, stage, "running")
                self.repository.append_log(run_id, stage, "pipeline", "INFO", f"Stage {stage} started", event_type="stage_status")

                self._run_stage(run_id, stage, run)

                latest = self.repository.get_run(run_id)
                if latest and latest["status"] == "cancelling":
                    self.repository.set_stage_status(run_id, stage, "success")
                    self.repository.set_run_status(run_id, "cancelled", current_stage_name=stage)
                    self.repository.append_log(run_id, stage, "pipeline", "INFO", "Run cancelled", event_type="run_status")
                    return

                self.repository.set_stage_status(run_id, stage, "success")
                self.repository.append_log(run_id, stage, "pipeline", "INFO", f"Stage {stage} succeeded", event_type="stage_status")

            self.repository.set_run_status(run_id, "success", current_stage_name=stages[-1])
            self.repository.append_log(run_id, None, "pipeline", "INFO", "Run completed successfully", event_type="run_status")
            self.repository.prune_logs_keep_last_10_runs()
        except Exception as exc:
            self.repository.set_stage_status(run_id, stage, "failed", error_message=str(exc))
            self.repository.set_run_status(run_id, "failed", current_stage_name=stage, error_message=str(exc))
            self.repository.append_log(run_id, stage, "pipeline", "ERROR", f"Stage failed: {exc}", event_type="stage_status")
            raise

    def _run_stage(self, run_id: int, stage: str, run: dict[str, Any]) -> None:
        if stage == "crawl":
            target_scope = run.get("target_scope")
            params = run.get("parameters_json") or {}
            if target_scope == "single_document" and params.get("document_url"):
                urls = [params["document_url"]]
            elif target_scope == "document_range" and params.get("document_range"):
                start = int(params["document_range"].get("start", 1))
                end = int(params["document_range"].get("end", start))
                urls = generate_scp_urls(start, end)
            else:
                urls = generate_scp_urls(1, TEST_CRAWL_LIMIT)
                self.repository.append_log(
                    run_id,
                    stage,
                    "pipeline",
                    "INFO",
                    f"Crawl limited to first {TEST_CRAWL_LIMIT} documents",
                    event_type="progress",
                )

            total = len(urls)
            stop_requested = False
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=0,
                total_items=total,
                items_completed=0,
                items_failed=0,
                message=f"crawl started, total={total}",
            )

            def on_crawl_document(
                processed: int,
                succeeded: int,
                failed: int,
                url: str,
                _result: Any,
                error: str | None,
            ) -> None:
                nonlocal stop_requested
                if not stop_requested and self.repository.has_pending_cancel_command(run_id):
                    self.repository.mark_active_run_cancelling(run_id)
                    self.repository.mark_cancel_commands_applied(run_id)
                    stop_requested = True
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        "Cancellation requested; stopping crawl at next boundary",
                        event_type="run_status",
                        document_url=url,
                        current_index=processed,
                    )

                self.repository.upsert_progress(
                    run_id,
                    stage,
                    current_index=processed,
                    total_items=total,
                    items_completed=succeeded,
                    items_failed=failed,
                    current_document_url=url,
                    current_item_label=url.rstrip("/").split("/")[-1],
                    message=f"crawl {processed}/{total}",
                )
                self.repository.set_stage_status(
                    run_id,
                    stage,
                    "running",
                    items_total=total,
                    items_completed=succeeded,
                    items_failed=failed,
                )

                should_log_info = processed == 1 or processed % 2 == 0 or processed == total
                if error:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "crawler",
                        "ERROR",
                        f"Failed {processed}/{total}: {url}",
                        event_type="progress",
                        document_url=url,
                        current_index=processed,
                    )
                elif should_log_info:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "crawler",
                        "INFO",
                        f"Crawled {processed}/{total}: {url}",
                        event_type="progress",
                        document_url=url,
                        current_index=processed,
                    )

            result = process_documents(
                urls,
                on_document=on_crawl_document,
                should_stop=lambda: stop_requested,
            )
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=result.processed,
                total_items=total,
                items_completed=result.succeeded,
                items_failed=result.failed,
                message="crawl stage completed",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=total,
                items_completed=result.succeeded,
                items_failed=result.failed,
            )
            return

        if stage == "extract":
            total_snapshots = 0
            succeeded = 0
            failed = 0

            def on_extract_snapshot(
                processed: int,
                total: int,
                succeeded_count: int,
                snapshot_id: str,
                _result: Any,
                error: str | None,
            ) -> None:
                nonlocal total_snapshots, succeeded, failed
                total_snapshots = total
                succeeded = succeeded_count
                failed = max(0, processed - succeeded_count)
                self.repository.upsert_progress(
                    run_id,
                    stage,
                    current_index=processed,
                    total_items=total,
                    items_completed=succeeded,
                    items_failed=failed,
                    current_item_label=snapshot_id,
                    message=f"extract {processed}/{total}",
                )
                self.repository.set_stage_status(
                    run_id,
                    stage,
                    "running",
                    items_total=total,
                    items_completed=succeeded,
                    items_failed=failed,
                )
                if error:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "extractor",
                        "ERROR",
                        f"Failed {processed}/{total}: snapshot {snapshot_id}",
                        event_type="progress",
                        current_index=processed,
                    )
                elif processed == 1 or processed % 2 == 0 or processed == total:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "extractor",
                        "INFO",
                        f"Processed {processed}/{total}: snapshot {snapshot_id}",
                        event_type="progress",
                        current_index=processed,
                    )

            extracted = process_pending_snapshots(limit=1000, on_snapshot=on_extract_snapshot)
            completed = len(extracted)
            if total_snapshots == 0:
                total_snapshots = completed
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=completed + failed,
                total_items=total_snapshots,
                items_completed=completed,
                items_failed=failed,
                message="extract stage completed",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=total_snapshots,
                items_completed=completed,
                items_failed=failed,
            )
            return

        if stage == "geocode":
            normalized = 0
            normalized_scanned = 0

            def on_normalize_progress(processed: int, updated: int, invalid: int) -> None:
                nonlocal normalized, normalized_scanned
                normalized = updated
                normalized_scanned = processed
                self.repository.append_log(
                    run_id,
                    stage,
                    "geocoder",
                    "INFO",
                    f"normalize scanned={processed} updated={updated} invalid={invalid}",
                    event_type="progress",
                    current_index=processed,
                )

            normalized = normalize_pending_mentions(limit=5000, on_progress=on_normalize_progress)
            geocode_processed = 0
            geocode_total = 0
            geocode_linked = 0
            geocode_unresolved = 0

            def on_geocode_mention(
                processed: int,
                total: int,
                geocoded_count: int,
                linked_count: int,
                mention: Any,
                status: str | None,
                error: str | None,
            ) -> None:
                nonlocal geocode_processed, geocode_total, geocode_linked, geocode_unresolved
                geocode_processed = processed
                geocode_total = total
                geocode_linked = linked_count
                geocode_unresolved = max(0, processed - linked_count)
                self.repository.upsert_progress(
                    run_id,
                    stage,
                    current_index=processed,
                    total_items=total,
                    items_completed=linked_count,
                    items_failed=geocode_unresolved,
                    current_item_label=getattr(mention, "normalized_location", None),
                    message=f"geocode {processed}/{total}, normalized={normalized}",
                )
                self.repository.set_stage_status(
                    run_id,
                    stage,
                    "running",
                    items_total=total,
                    items_completed=linked_count,
                    items_failed=geocode_unresolved,
                )
                if error:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "geocoder",
                        "ERROR",
                        f"Failed {processed}/{total}: {getattr(mention, 'normalized_location', 'unknown')}",
                        event_type="progress",
                        current_index=processed,
                    )
                elif processed == 1 or processed % 10 == 0 or processed == total:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "geocoder",
                        "INFO",
                        (
                            f"Processed {processed}/{total}: {getattr(mention, 'normalized_location', 'unknown')} "
                            f"status={status} geocoded={geocoded_count} linked={linked_count}"
                        ),
                        event_type="progress",
                        current_index=processed,
                    )

            geo_result = process_pending_mentions(limit=5000, on_mention=on_geocode_mention)
            if geocode_total == 0:
                geocode_total = geo_result.processed
            if geocode_processed == 0:
                geocode_processed = geo_result.processed
                geocode_linked = geo_result.linked
                geocode_unresolved = geo_result.unresolved
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=geocode_processed,
                total_items=geocode_total,
                items_completed=geocode_linked,
                items_failed=geocode_unresolved,
                message=f"geocode stage completed, normalized={normalized}, scanned={normalized_scanned}",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=geocode_total,
                items_completed=geocode_linked,
                items_failed=geocode_unresolved,
            )
            return

        if stage == "analytics":
            processed = 0

            def on_analytics_step(table_name: str, rows: int) -> None:
                nonlocal processed
                processed += 1
                self.repository.upsert_progress(
                    run_id,
                    stage,
                    current_index=processed,
                    total_items=3,
                    items_completed=processed,
                    items_failed=0,
                    current_item_label=table_name,
                    message=f"analytics {processed}/3",
                )
                self.repository.append_log(
                    run_id,
                    stage,
                    "analytics",
                    "INFO",
                    f"rebuilt {table_name}, rows={rows}",
                    event_type="progress",
                    current_index=processed,
                )

            stats = rebuild_analytics(on_step=on_analytics_step)
            total = sum(stats.values())
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=processed,
                total_items=3,
                items_completed=processed,
                items_failed=0,
                message=f"analytics stage completed, rows={total}",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=3,
                items_completed=processed,
                items_failed=0,
            )
            return

        if stage == "export":
            processed = 0
            failed = 0

            def on_export_table(table_name: str, status: str, error: str | None) -> None:
                nonlocal processed, failed
                if status == "succeeded":
                    processed += 1
                if status == "failed":
                    failed += 1
                level = "INFO" if status in ("started", "succeeded") else "ERROR"
                msg = f"export {table_name}: {status}"
                if error:
                    msg = f"{msg} ({error})"
                self.repository.append_log(
                    run_id,
                    stage,
                    "export",
                    level,
                    msg,
                    event_type="progress",
                    current_index=processed + failed,
                )
                self.repository.upsert_progress(
                    run_id,
                    stage,
                    current_index=processed + failed,
                    total_items=3,
                    items_completed=processed,
                    items_failed=failed,
                    current_item_label=table_name,
                    message=f"export {processed + failed}/3",
                )
                self.repository.set_stage_status(
                    run_id,
                    stage,
                    "running",
                    items_total=3,
                    items_completed=processed,
                    items_failed=failed,
                )

            export_all_bi_tables(mode="incremental", on_table=on_export_table)
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=processed + failed,
                total_items=3,
                items_completed=processed,
                items_failed=failed,
                message="export stage completed",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=3,
                items_completed=processed,
                items_failed=failed,
            )
            return

        raise ValueError(f"Unknown stage {stage}")
