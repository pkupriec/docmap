from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.control import orchestrator as orchestrator_module
from services.control.orchestrator import ControlOrchestrator


class FakeRepo:
    def __init__(self) -> None:
        self.active_run = None
        self.runs = {
            1: {
                "id": 1,
                "pipeline_type": "full_pipeline",
                "target_scope": "all",
                "parameters_json": {"pipeline_type": "full_pipeline", "target_scope": "all"},
                "status": "failed",
            }
        }
        self.completed: list[tuple[int, str, str | None]] = []
        self.deferred: dict[int, dict] = {}
        self.created_runs: list[dict] = []
        self.reset_calls: list[tuple[int, str]] = []
        self.run_status_updates: list[tuple[int, str, bool]] = []
        self.stage_rows: dict[tuple[int, str], dict[str, object]] = {}
        self.progress_rows: dict[tuple[int, str], dict[str, object]] = {}

    def poll_next_command(self):
        return None

    def find_active_run(self):
        return self.active_run

    def mark_active_run_cancelling(self, run_id: int) -> None:
        if self.active_run and self.active_run["id"] == run_id:
            self.active_run["status"] = "cancelling"

    def defer_command(self, command_id: int, payload_json: dict) -> None:
        self.deferred[command_id] = payload_json

    def create_run(self, **kwargs):
        self.created_runs.append(kwargs)
        run_id = len(self.runs) + 1
        self.runs[run_id] = {
            "id": run_id,
            "pipeline_type": kwargs["pipeline_type"],
            "target_scope": kwargs["target_scope"],
            "parameters_json": kwargs["parameters_json"],
            "status": "pending",
        }
        return run_id

    def append_log(self, *args, **kwargs):
        return 1

    def complete_command(self, command_id: int, status: str, error_message: str | None = None):
        self.completed.append((command_id, status, error_message))

    def run_exists(self, run_id: int) -> bool:
        return run_id in self.runs

    def get_run(self, run_id: int):
        return self.runs.get(run_id)

    def stage_exists(self, run_id: int, stage_name: str) -> bool:
        return run_id in self.runs and stage_name in ("crawl", "extract", "geocode", "analytics", "export")

    def reset_stages_from(self, run_id: int, stage_name: str) -> None:
        self.reset_calls.append((run_id, stage_name))

    def reset_stages_after(self, run_id: int, stage_name: str) -> None:
        self.reset_calls.append((run_id, stage_name))

    def reject_pending_cancel_commands(self, run_id: int, reason: str) -> int:
        return 0

    def set_run_status(self, run_id: int, status: str, **kwargs) -> None:
        self.runs[run_id]["status"] = status
        self.run_status_updates.append((run_id, status, bool(kwargs.get("clear_finished"))))

    def list_stages(self, run_id: int):
        return []

    def set_stage_status(self, *args, **kwargs):
        return None

    def upsert_progress(self, *args, **kwargs):
        return None

    def prune_logs_keep_last_10_runs(self):
        return 0

    def get_stage_run(self, run_id: int, stage_name: str):
        return self.stage_rows.get((run_id, stage_name))

    def get_progress_entry(self, run_id: int, stage_name: str):
        return self.progress_rows.get((run_id, stage_name))


def test_start_run_replace_semantics_sets_active_to_cancelling_then_defers() -> None:
    repo = FakeRepo()
    repo.active_run = {"id": 99, "status": "running"}
    orchestrator = ControlOrchestrator(repository=repo)

    command = {
        "id": 10,
        "command_type": "start_run",
        "payload_json": {"pipeline_type": "full_pipeline", "target_scope": "all"},
        "requested_by": None,
    }

    orchestrator._apply_command(command)

    assert repo.active_run["status"] == "cancelling"
    assert repo.deferred[10]["deferred"] is True
    assert repo.created_runs == []


def test_retry_run_creates_new_run_and_keeps_old_run_unchanged() -> None:
    repo = FakeRepo()
    orchestrator = ControlOrchestrator(repository=repo)

    command = {
        "id": 11,
        "command_type": "retry_run",
        "pipeline_run_id": 1,
        "payload_json": {"options": {"force": True}},
        "requested_by": None,
    }

    orchestrator._apply_command(command)

    assert len(repo.created_runs) == 1
    created = repo.created_runs[0]
    assert created["replacement_for_run_id"] == 1
    assert repo.runs[1]["status"] == "failed"
    assert repo.completed[-1][1] == "applied"


def test_retry_stage_resets_selected_and_downstream() -> None:
    repo = FakeRepo()
    orchestrator = ControlOrchestrator(repository=repo)

    command = {
        "id": 12,
        "command_type": "retry_stage",
        "pipeline_run_id": 1,
        "stage_name": "extract",
        "payload_json": {},
        "requested_by": None,
    }

    orchestrator._apply_command(command)

    assert repo.reset_calls == [(1, "extract")]
    assert repo.run_status_updates[-1] == (1, "pending", True)
    assert repo.completed[-1][1] == "applied"


def test_resume_stage_on_completed_progress_falls_back_to_full_retry() -> None:
    repo = FakeRepo()
    repo.stage_rows[(1, "analytics")] = {"status": "success"}
    repo.progress_rows[(1, "analytics")] = {"current_index": 5, "total_items": 5}
    orchestrator = ControlOrchestrator(repository=repo)

    command = {
        "id": 14,
        "command_type": "retry_stage",
        "pipeline_run_id": 1,
        "stage_name": "analytics",
        "payload_json": {"resume": True},
        "requested_by": None,
    }

    orchestrator._apply_command(command)

    assert repo.reset_calls == [(1, "analytics")]
    assert repo.run_status_updates[-1] == (1, "pending", True)
    assert repo.completed[-1][1] == "applied"


def test_cancel_run_soft_cancel_marks_cancelling() -> None:
    repo = FakeRepo()
    repo.runs[2] = {
        "id": 2,
        "pipeline_type": "full_pipeline",
        "target_scope": "all",
        "parameters_json": {},
        "status": "running",
    }
    repo.active_run = repo.runs[2]
    orchestrator = ControlOrchestrator(repository=repo)

    command = {
        "id": 13,
        "command_type": "cancel_run",
        "pipeline_run_id": 2,
        "payload_json": {},
    }
    orchestrator._apply_command(command)

    assert repo.runs[2]["status"] == "cancelling"
    assert repo.completed[-1][1] == "applied"


def test_soft_cancel_completes_current_stage_then_marks_run_cancelled(monkeypatch) -> None:
    repo = FakeRepo()
    repo.runs[3] = {
        "id": 3,
        "pipeline_type": "crawl_only",
        "target_scope": "all",
        "parameters_json": {},
        "status": "pending",
        "current_stage_name": None,
    }
    orchestrator = ControlOrchestrator(repository=repo)

    def _cancel_after_stage(run_id: int, stage: str, run: dict) -> None:
        repo.runs[run_id]["status"] = "cancelling"

    monkeypatch.setattr(orchestrator, "_run_stage", _cancel_after_stage)
    orchestrator._execute_run(3)

    assert repo.runs[3]["status"] == "cancelled"


class _StageRepo:
    def __init__(self) -> None:
        self.logs: list[str] = []

    def get_progress_entry(self, _run_id: int, _stage: str):
        return {}

    def upsert_progress(self, *args, **kwargs):
        return None

    def set_stage_status(self, *args, **kwargs):
        return None

    def has_pending_cancel_command(self, _run_id: int) -> bool:
        return False

    def has_pending_operator_command_for_other_run(self, _run_id: int) -> bool:
        return False

    def mark_active_run_cancelling(self, _run_id: int) -> None:
        return None

    def mark_cancel_commands_applied(self, _run_id: int) -> None:
        return None

    def append_log(self, _run_id: int, _stage: str | None, _service: str, _level: str, message: str, **kwargs):
        self.logs.append(message)
        return 1


def test_crawl_single_document_forces_resnapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _StageRepo()
    orchestrator = ControlOrchestrator(repository=repo)
    captured: dict[str, object] = {}

    def _fake_process_documents(urls, **kwargs):
        captured["urls"] = urls
        captured["resnapshot"] = kwargs.get("resnapshot")
        return SimpleNamespace(processed=len(urls), succeeded=len(urls), failed=0)

    monkeypatch.setattr(orchestrator_module, "process_documents", _fake_process_documents)

    run = {
        "target_scope": "single_document",
        "parameters_json": {
            "document_url": "https://scp-wiki.wikidot.com/scp-173",
            "options": {"process_unprocessed_only": True},
        },
    }
    orchestrator._run_stage(1, "crawl", run)

    assert captured["urls"] == ["https://scp-wiki.wikidot.com/scp-173"]
    assert captured["resnapshot"] is True


def test_crawl_unprocessed_mode_filters_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _StageRepo()
    orchestrator = ControlOrchestrator(repository=repo)
    captured: dict[str, object] = {}

    all_urls = [
        "https://scp-wiki.wikidot.com/scp-001",
        "https://scp-wiki.wikidot.com/scp-002",
        "https://scp-wiki.wikidot.com/scp-003",
    ]
    filtered_urls = [all_urls[1]]

    monkeypatch.setattr(orchestrator_module, "generate_scp_urls", lambda _start, _end: all_urls)
    monkeypatch.setattr(orchestrator_module, "filter_unprocessed_urls", lambda urls, **kwargs: filtered_urls)

    def _fake_process_documents(urls, **kwargs):
        captured["urls"] = urls
        captured["resnapshot"] = kwargs.get("resnapshot")
        return SimpleNamespace(processed=len(urls), succeeded=len(urls), failed=0)

    monkeypatch.setattr(orchestrator_module, "process_documents", _fake_process_documents)

    run = {
        "target_scope": "all",
        "parameters_json": {"options": {"process_unprocessed_only": True}},
    }
    orchestrator._run_stage(1, "crawl", run)

    assert captured["urls"] == filtered_urls
    assert captured["resnapshot"] is False


def test_extract_full_mode_uses_all_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _StageRepo()
    orchestrator = ControlOrchestrator(repository=repo)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        orchestrator_module,
        "process_all_snapshots",
        lambda **kwargs: captured.update(kwargs) or [],
    )
    monkeypatch.setattr(
        orchestrator_module,
        "process_pending_snapshots",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("pending extractor path must not be used in full mode")),
    )

    run = {
        "target_scope": "all",
        "parameters_json": {"options": {}},
    }
    orchestrator._run_stage(1, "extract", run)

    assert captured["offset"] == 0
    assert "on_snapshot" in captured


def test_extract_unprocessed_mode_uses_pending_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _StageRepo()
    orchestrator = ControlOrchestrator(repository=repo)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        orchestrator_module,
        "process_pending_snapshots",
        lambda **kwargs: captured.update(kwargs) or [],
    )
    monkeypatch.setattr(
        orchestrator_module,
        "process_all_snapshots",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("full extractor path must not be used in unprocessed mode")),
    )

    run = {
        "target_scope": "all",
        "parameters_json": {"options": {"process_unprocessed_only": True}},
    }
    orchestrator._run_stage(1, "extract", run)

    assert captured["offset"] == 0
    assert "on_snapshot" in captured


def test_geocode_full_mode_uses_all_mentions(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _StageRepo()
    orchestrator = ControlOrchestrator(repository=repo)
    captured: dict[str, object] = {}

    monkeypatch.setattr(orchestrator_module, "count_all_mentions", lambda _conn: 10)
    monkeypatch.setattr(orchestrator_module, "count_pending_mentions", lambda _conn: 3)
    monkeypatch.setattr(orchestrator_module, "normalize_pending_mentions", lambda **kwargs: 0)
    monkeypatch.setattr(
        orchestrator_module,
        "process_all_mentions",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(processed=0, linked=0, unresolved=0),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "process_pending_mentions",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("pending geocoder path must not be used in full mode")),
    )

    run = {
        "target_scope": "all",
        "parameters_json": {"options": {}},
    }
    orchestrator._run_stage(1, "geocode", run)

    assert captured["offset"] == 0
    assert captured["reset_existing_links"] is True
    assert captured["refresh_missing_identity"] is False
    assert "on_mention" in captured


def test_geocode_full_mode_passes_refresh_geo_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _StageRepo()
    orchestrator = ControlOrchestrator(repository=repo)
    captured: dict[str, object] = {}

    monkeypatch.setattr(orchestrator_module, "count_all_mentions", lambda _conn: 10)
    monkeypatch.setattr(orchestrator_module, "count_pending_mentions", lambda _conn: 3)
    monkeypatch.setattr(orchestrator_module, "normalize_pending_mentions", lambda **kwargs: 0)
    monkeypatch.setattr(
        orchestrator_module,
        "process_all_mentions",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(processed=0, linked=0, unresolved=0),
    )

    run = {
        "target_scope": "all",
        "parameters_json": {"options": {"refresh_geo_identity": True}},
    }
    orchestrator._run_stage(1, "geocode", run)

    assert captured["refresh_missing_identity"] is True


def test_geocode_unprocessed_mode_uses_pending_mentions(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _StageRepo()
    orchestrator = ControlOrchestrator(repository=repo)
    captured: dict[str, object] = {}

    monkeypatch.setattr(orchestrator_module, "count_pending_mentions", lambda _conn: 4)
    monkeypatch.setattr(orchestrator_module, "count_all_mentions", lambda _conn: 11)
    monkeypatch.setattr(orchestrator_module, "normalize_pending_mentions", lambda **kwargs: 0)
    monkeypatch.setattr(
        orchestrator_module,
        "process_pending_mentions",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(processed=0, linked=0, unresolved=0),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "process_all_mentions",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("full geocoder path must not be used in unprocessed mode")),
    )

    run = {
        "target_scope": "all",
        "parameters_json": {"options": {"process_unprocessed_only": True}},
    }
    orchestrator._run_stage(1, "geocode", run)

    assert captured["offset"] == 0
    assert "on_mention" in captured


def test_enqueue_followup_analytics_for_refresh_geocode_only() -> None:
    repo = FakeRepo()
    orchestrator = ControlOrchestrator(repository=repo)
    run = {
        "id": 42,
        "pipeline_type": "geocode_only",
        "target_scope": "all",
        "parameters_json": {"options": {"refresh_geo_identity": True}},
    }

    orchestrator._enqueue_followup_analytics_if_needed(42, run)

    assert len(repo.created_runs) == 1
    created = repo.created_runs[0]
    assert created["pipeline_type"] == "analytics_only"
    assert created["target_scope"] == "all"


def test_enqueue_followup_analytics_skips_unprocessed_mode() -> None:
    repo = FakeRepo()
    orchestrator = ControlOrchestrator(repository=repo)
    run = {
        "id": 43,
        "pipeline_type": "geocode_only",
        "target_scope": "all",
        "parameters_json": {"options": {"refresh_geo_identity": True, "process_unprocessed_only": True}},
    }

    orchestrator._enqueue_followup_analytics_if_needed(43, run)

    assert repo.created_runs == []
