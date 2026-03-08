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
        if active["status"] == "cancelling" and not active.get("current_stage_name"):
            self.repository.set_run_status(active["id"], "cancelled", current_stage_name=None)
            self.repository.append_log(active["id"], None, "pipeline", "INFO", "Run cancelled before start", event_type="run_status")

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
                urls = generate_scp_urls(1, 7999)

            total = len(urls)
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

            result = process_documents(urls, on_document=on_crawl_document)
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
            extracted = process_pending_snapshots(limit=1000)
            completed = len(extracted)
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=completed,
                total_items=completed,
                items_completed=completed,
                items_failed=0,
                message="extract stage completed",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=completed,
                items_completed=completed,
                items_failed=0,
            )
            return

        if stage == "geocode":
            normalized = normalize_pending_mentions(limit=5000)
            geo_result = process_pending_mentions(limit=5000)
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=geo_result.processed,
                total_items=geo_result.processed,
                items_completed=geo_result.linked,
                items_failed=geo_result.unresolved,
                message=f"geocode stage completed, normalized={normalized}",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=geo_result.processed,
                items_completed=geo_result.linked,
                items_failed=geo_result.unresolved,
            )
            return

        if stage == "analytics":
            stats = rebuild_analytics()
            total = sum(stats.values())
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=total,
                total_items=total,
                items_completed=total,
                items_failed=0,
                message="analytics stage completed",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=total,
                items_completed=total,
                items_failed=0,
            )
            return

        if stage == "export":
            export_all_bi_tables(mode="incremental")
            self.repository.upsert_progress(
                run_id,
                stage,
                current_index=3,
                total_items=3,
                items_completed=3,
                items_failed=0,
                message="export stage completed",
            )
            self.repository.set_stage_status(
                run_id,
                stage,
                "running",
                items_total=3,
                items_completed=3,
                items_failed=0,
            )
            return

        raise ValueError(f"Unknown stage {stage}")
