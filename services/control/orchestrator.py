from __future__ import annotations

import logging
import os
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


def _stage_item_limit() -> int | None:
    raw_value = os.getenv("DOCMAP_STAGE_ITEM_LIMIT")
    if raw_value is None:
        return 20
    raw_value = raw_value.strip()
    if raw_value == "" or raw_value.lower() == "all" or raw_value == "0":
        return None
    try:
        parsed = int(raw_value)
        if parsed > 0:
            return parsed
    except ValueError:
        pass
    logger.warning("control.orchestrator.invalid_stage_item_limit value=%s fallback=20", raw_value)
    return 20


TEST_STAGE_ITEM_LIMIT = _stage_item_limit()


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

        if payload.get("resume"):
            progress = self.repository.get_progress_entry(run_id, stage_name) or {}
            cleared = self.repository.reject_pending_cancel_commands(run_id, reason="stale after stage resume")
            self.repository.reset_stages_after(run_id, stage_name)
            self.repository.set_run_status(run_id, "pending", current_stage_name=None, error_message=None, clear_finished=True)
            self.repository.set_stage_status(run_id, stage_name, "pending", error_message=None)
            self.repository.append_log(
                run_id,
                stage_name,
                "pipeline",
                "INFO",
                (
                    f"Stage resume requested for {stage_name}; continue from index="
                    f"{int(progress.get('current_index') or 0)}"
                ),
                event_type="stage_status",
                payload_json={"stages_reset": downstream_stages(stage_name)[1:], "cancel_commands_cleared": cleared},
            )
        else:
            cleared = self.repository.reject_pending_cancel_commands(run_id, reason="stale after stage retry")
            self.repository.reset_stages_from(run_id, stage_name)
            self.repository.set_run_status(run_id, "pending", current_stage_name=None, error_message=None, clear_finished=True)
            self.repository.append_log(
                run_id,
                stage_name,
                "pipeline",
                "INFO",
                f"Stage retry requested from {stage_name}; downstream stages reset",
                event_type="stage_status",
                payload_json={"stages_reset": downstream_stages(stage_name), "cancel_commands_cleared": cleared},
            )
        self.repository.complete_command(command["id"], "applied")

    def _execute_run(self, run_id: int) -> None:
        run = self.repository.get_run(run_id)
        if not run:
            return

        stages = STAGES_BY_PIPELINE_TYPE[run["pipeline_type"]]
        self.repository.set_run_status(run_id, "running", current_stage_name=None)
        self.repository.append_log(run_id, None, "pipeline", "INFO", "Run started", event_type="run_status")

        try:
            for stage in stages:
                stage_row = self.repository.get_stage_run(run_id, stage)
                if stage_row and stage_row["status"] == "success":
                    continue
                self.repository.set_run_status(run_id, "running", current_stage_name=stage)
                self.repository.set_stage_status(run_id, stage, "running")
                self.repository.append_log(run_id, stage, "pipeline", "INFO", f"Stage {stage} started", event_type="stage_status")

                self._run_stage(run_id, stage, run)

                latest = self.repository.get_run(run_id)
                if latest and latest["status"] == "cancelling":
                    self.repository.set_stage_status(run_id, stage, "skipped", error_message="cancelled")
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
                crawl_end = TEST_STAGE_ITEM_LIMIT if TEST_STAGE_ITEM_LIMIT is not None else 7999
                urls = generate_scp_urls(1, crawl_end)
                if TEST_STAGE_ITEM_LIMIT is None:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        "Stage processing limit disabled (all items)",
                        event_type="progress",
                    )
                else:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        f"Stage processing limited to first {TEST_STAGE_ITEM_LIMIT} items",
                        event_type="progress",
                    )

            total = len(urls)
            progress = self.repository.get_progress_entry(run_id, stage) or {}
            start_index = int(progress.get("current_index") or 0)
            base_completed = int(progress.get("items_completed") or 0)
            base_failed = int(progress.get("items_failed") or 0)
            if start_index > total:
                start_index = total
            urls_to_process = urls[start_index:]
            stop_requested = False
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=start_index,
                total_items=total,
                items_completed=base_completed,
                items_failed=base_failed,
                message=f"crawl started, total={total}, from={start_index}",
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
                overall_processed = start_index + processed
                overall_succeeded = base_completed + succeeded
                overall_failed = base_failed + failed
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
                        current_index=overall_processed,
                    )
                if not stop_requested and self.repository.has_pending_operator_command_for_other_run(run_id):
                    self.repository.mark_active_run_cancelling(run_id)
                    stop_requested = True
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        "Queued command detected; stopping current stage at next boundary",
                        event_type="run_status",
                        document_url=url,
                        current_index=overall_processed,
                    )

                self.repository.upsert_progress(
                    run_id,
                    stage,
                    current_index=overall_processed,
                    total_items=total,
                    items_completed=overall_succeeded,
                    items_failed=overall_failed,
                    current_document_url=url,
                    current_item_label=url.rstrip("/").split("/")[-1],
                    message=f"crawl {overall_processed}/{total}",
                )
                self.repository.set_stage_status(
                    run_id,
                    stage,
                    "running",
                    items_total=total,
                    items_completed=overall_succeeded,
                    items_failed=overall_failed,
                )

                should_log_info = overall_processed == 1 or overall_processed % 2 == 0 or overall_processed == total
                if error:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "crawler",
                        "ERROR",
                        f"Failed {overall_processed}/{total}: {url}",
                        event_type="progress",
                        document_url=url,
                        current_index=overall_processed,
                    )
                elif should_log_info:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "crawler",
                        "INFO",
                        f"Crawled {overall_processed}/{total}: {url}",
                        event_type="progress",
                        document_url=url,
                        current_index=overall_processed,
                    )

            result = process_documents(
                urls_to_process,
                on_document=on_crawl_document,
                should_stop=lambda: stop_requested,
            )
            final_completed = base_completed + result.succeeded
            final_failed = base_failed + result.failed
            final_processed = start_index + result.processed
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=final_processed,
                total_items=total,
                items_completed=final_completed,
                items_failed=final_failed,
                message="crawl stage completed",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=total,
                items_completed=final_completed,
                items_failed=final_failed,
            )
            return

        if stage == "extract":
            progress = self.repository.get_progress_entry(run_id, stage) or {}
            start_index = int(progress.get("current_index") or 0)
            base_completed = int(progress.get("items_completed") or 0)
            base_failed = int(progress.get("items_failed") or 0)
            stop_requested = False
            total_snapshots = 0
            succeeded = base_completed
            failed = base_failed

            def on_extract_snapshot(
                processed: int,
                total: int,
                succeeded_count: int,
                snapshot_id: str,
                _result: Any,
                error: str | None,
            ) -> None:
                nonlocal total_snapshots, succeeded, failed, stop_requested
                if not stop_requested and self.repository.has_pending_cancel_command(run_id):
                    self.repository.mark_active_run_cancelling(run_id)
                    self.repository.mark_cancel_commands_applied(run_id)
                    stop_requested = True
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        "Cancellation requested; stopping extract at next boundary",
                        event_type="run_status",
                        current_index=start_index + processed,
                    )
                if not stop_requested and self.repository.has_pending_operator_command_for_other_run(run_id):
                    self.repository.mark_active_run_cancelling(run_id)
                    stop_requested = True
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        "Queued command detected; stopping current stage at next boundary",
                        event_type="run_status",
                        current_index=start_index + processed,
                    )
                total_snapshots = start_index + total
                succeeded = base_completed + succeeded_count
                failed = base_failed + max(0, processed - succeeded_count)
                overall_processed = start_index + processed
                self.repository.upsert_progress(
                    run_id,
                    stage,
                    current_index=overall_processed,
                    total_items=total_snapshots,
                    items_completed=succeeded,
                    items_failed=failed,
                    current_item_label=snapshot_id,
                    message=f"extract {overall_processed}/{total_snapshots}",
                )
                self.repository.set_stage_status(
                    run_id,
                    stage,
                    "running",
                    items_total=total_snapshots,
                    items_completed=succeeded,
                    items_failed=failed,
                )
                if error:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "extractor",
                        "ERROR",
                        f"Failed {overall_processed}/{total_snapshots}: snapshot {snapshot_id}",
                        event_type="progress",
                        current_index=overall_processed,
                    )
                elif overall_processed == 1 or overall_processed % 2 == 0 or processed == total:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "extractor",
                        "INFO",
                        f"Processed {overall_processed}/{total_snapshots}: snapshot {snapshot_id}",
                        event_type="progress",
                        current_index=overall_processed,
                    )

            extract_limit = TEST_STAGE_ITEM_LIMIT if TEST_STAGE_ITEM_LIMIT is not None else 2147483647
            if TEST_STAGE_ITEM_LIMIT is None:
                self.repository.append_log(
                    run_id,
                    stage,
                    "pipeline",
                    "INFO",
                    "Stage processing limit disabled (all items)",
                    event_type="progress",
                )
            else:
                self.repository.append_log(
                    run_id,
                    stage,
                    "pipeline",
                    "INFO",
                    f"Stage processing limited to first {TEST_STAGE_ITEM_LIMIT} items",
                    event_type="progress",
                )
            extracted = process_pending_snapshots(
                limit=extract_limit,
                offset=start_index,
                on_snapshot=on_extract_snapshot,
                should_stop=lambda: stop_requested,
            )
            completed = base_completed + len(extracted)
            if total_snapshots == 0:
                total_snapshots = start_index + len(extracted)
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=start_index + len(extracted) + (failed - base_failed),
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
            progress = self.repository.get_progress_entry(run_id, stage) or {}
            start_index = int(progress.get("current_index") or 0)
            base_linked = int(progress.get("items_completed") or 0)
            base_failed = int(progress.get("items_failed") or 0)
            stop_requested = False
            normalized = 0
            normalized_scanned = 0

            def on_normalize_progress(processed: int, updated: int, invalid: int) -> None:
                nonlocal normalized, normalized_scanned, stop_requested
                if not stop_requested and self.repository.has_pending_cancel_command(run_id):
                    self.repository.mark_active_run_cancelling(run_id)
                    self.repository.mark_cancel_commands_applied(run_id)
                    stop_requested = True
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        "Cancellation requested; stopping geocode at next boundary",
                        event_type="run_status",
                        current_index=start_index,
                    )
                if not stop_requested and self.repository.has_pending_operator_command_for_other_run(run_id):
                    self.repository.mark_active_run_cancelling(run_id)
                    stop_requested = True
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        "Queued command detected; stopping current stage at next boundary",
                        event_type="run_status",
                        current_index=start_index,
                    )
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

            geocode_limit = TEST_STAGE_ITEM_LIMIT if TEST_STAGE_ITEM_LIMIT is not None else 2147483647
            if TEST_STAGE_ITEM_LIMIT is None:
                self.repository.append_log(
                    run_id,
                    stage,
                    "pipeline",
                    "INFO",
                    "Stage processing limit disabled (all items)",
                    event_type="progress",
                )
            else:
                self.repository.append_log(
                    run_id,
                    stage,
                    "pipeline",
                    "INFO",
                    f"Stage processing limited to first {TEST_STAGE_ITEM_LIMIT} items",
                    event_type="progress",
                )
            if start_index > 0:
                self.repository.append_log(
                    run_id,
                    stage,
                    "geocoder",
                    "INFO",
                    f"Resume mode: normalization step skipped, continue from index={start_index}",
                    event_type="progress",
                    current_index=start_index,
                )
            else:
                normalized = normalize_pending_mentions(limit=geocode_limit, on_progress=on_normalize_progress)
                if stop_requested:
                    return
            geocode_processed = start_index
            geocode_total = 0
            geocode_linked = base_linked
            geocode_unresolved = base_failed

            def on_geocode_mention(
                processed: int,
                total: int,
                geocoded_count: int,
                linked_count: int,
                mention: Any,
                status: str | None,
                error: str | None,
            ) -> None:
                nonlocal geocode_processed, geocode_total, geocode_linked, geocode_unresolved, stop_requested
                if not stop_requested and self.repository.has_pending_cancel_command(run_id):
                    self.repository.mark_active_run_cancelling(run_id)
                    self.repository.mark_cancel_commands_applied(run_id)
                    stop_requested = True
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        "Cancellation requested; stopping geocode at next boundary",
                        event_type="run_status",
                        current_index=start_index + processed,
                    )
                if not stop_requested and self.repository.has_pending_operator_command_for_other_run(run_id):
                    self.repository.mark_active_run_cancelling(run_id)
                    stop_requested = True
                    self.repository.append_log(
                        run_id,
                        stage,
                        "pipeline",
                        "INFO",
                        "Queued command detected; stopping current stage at next boundary",
                        event_type="run_status",
                        current_index=start_index + processed,
                    )
                geocode_processed = start_index + processed
                geocode_total = start_index + total
                geocode_linked = base_linked + linked_count
                geocode_unresolved = base_failed + max(0, processed - linked_count)
                self.repository.upsert_progress(
                    run_id,
                    stage,
                    current_index=geocode_processed,
                    total_items=geocode_total,
                    items_completed=geocode_linked,
                    items_failed=geocode_unresolved,
                    current_item_label=getattr(mention, "normalized_location", None),
                    message=f"geocode {geocode_processed}/{geocode_total}, normalized={normalized}",
                )
                self.repository.set_stage_status(
                    run_id,
                    stage,
                    "running",
                    items_total=geocode_total,
                    items_completed=geocode_linked,
                    items_failed=geocode_unresolved,
                )
                if error:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "geocoder",
                        "ERROR",
                        f"Failed {geocode_processed}/{geocode_total}: {getattr(mention, 'normalized_location', 'unknown')}",
                        event_type="progress",
                        current_index=geocode_processed,
                    )
                elif geocode_processed == 1 or geocode_processed % 10 == 0 or processed == total:
                    self.repository.append_log(
                        run_id,
                        stage,
                        "geocoder",
                        "INFO",
                        (
                            f"Processed {geocode_processed}/{geocode_total}: {getattr(mention, 'normalized_location', 'unknown')} "
                            f"status={status} geocoded={geocoded_count} linked={linked_count}"
                        ),
                        event_type="progress",
                        current_index=geocode_processed,
                    )

            geo_result = process_pending_mentions(
                limit=geocode_limit,
                offset=start_index,
                on_mention=on_geocode_mention,
                should_stop=lambda: stop_requested,
            )
            if geocode_total == 0:
                geocode_total = start_index + geo_result.processed
            if geocode_processed == start_index:
                geocode_processed = start_index + geo_result.processed
                geocode_linked = base_linked + geo_result.linked
                geocode_unresolved = base_failed + geo_result.unresolved
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
            progress = self.repository.get_progress_entry(run_id, stage) or {}
            start_index = int(progress.get("current_index") or 0)
            if start_index > 3:
                start_index = 3
            processed = start_index

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

            if start_index > 0:
                self.repository.append_log(
                    run_id,
                    stage,
                    "analytics",
                    "INFO",
                    f"Resume mode: continue from step {start_index}/3",
                    event_type="progress",
                    current_index=start_index,
                )
            stats = rebuild_analytics(on_step=on_analytics_step, start_index=start_index)
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
            progress = self.repository.get_progress_entry(run_id, stage) or {}
            start_index = int(progress.get("items_completed") or 0)
            if start_index > 3:
                start_index = 3
            processed = start_index
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

            if start_index > 0:
                self.repository.append_log(
                    run_id,
                    stage,
                    "export",
                    "INFO",
                    f"Resume mode: continue from step {start_index}/3",
                    event_type="progress",
                    current_index=start_index,
                )
            export_all_bi_tables(mode="incremental", on_table=on_export_table, start_index=start_index)
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
