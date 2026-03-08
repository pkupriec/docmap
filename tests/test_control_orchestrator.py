from __future__ import annotations

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
