from __future__ import annotations

from fastapi.testclient import TestClient

from services.control import api
from services.control.api import create_app
from services.control.repository import DuplicatePendingCommandError


class DummyOrchestrator:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class ApiRepo:
    def __init__(self) -> None:
        pass

    def list_runs(self, limit, status, pipeline_type):
        return [{"id": 1, "pipeline_type": "full_pipeline", "status": "pending", "target_scope": "all", "parameters_json": {}, "created_at": "2026-03-08T00:00:00Z", "updated_at": "2026-03-08T00:00:00Z", "current_stage_name": None, "requested_by": None, "replacement_for_run_id": None, "started_at": None, "finished_at": None, "error_message": None}]

    def enqueue_command(self, *args, **kwargs):
        if kwargs.get("dedupe_key") == "dup":
            raise DuplicatePendingCommandError()
        return 7

    def run_exists(self, run_id: int):
        return True

    def stage_exists(self, run_id: int, stage_name: str):
        return True

    def get_run(self, run_id: int):
        return {
            "id": run_id,
            "pipeline_type": "full_pipeline",
            "status": "running",
            "target_scope": "all",
            "parameters_json": {},
            "current_stage_name": "crawl",
            "requested_by": None,
            "replacement_for_run_id": None,
            "started_at": None,
            "finished_at": None,
            "error_message": None,
            "created_at": "2026-03-08T00:00:00Z",
            "updated_at": "2026-03-08T00:00:00Z",
        }

    def list_stages(self, run_id: int):
        return []

    def list_progress(self, run_id: int):
        return []

    def list_logs(self, run_id: int, **kwargs):
        return [
            {"id": 1, "pipeline_run_id": run_id, "service_name": "pipeline", "level": "INFO", "message": "a", "created_at": "2026-03-08T00:00:00Z"},
            {"id": 2, "pipeline_run_id": run_id, "service_name": "pipeline", "level": "INFO", "message": "b", "created_at": "2026-03-08T00:00:01Z"},
        ]

    def get_command(self, command_id: int):
        return {"id": command_id, "command_type": "start_run", "status": "pending", "payload_json": {}, "requested_at": "2026-03-08T00:00:00Z"}

    def get_latest_state_snapshot(self, run_id: int, after_log_id: int = 0):
        logs = [] if after_log_id >= 1 else [{"id": 1, "pipeline_run_id": run_id, "service_name": "pipeline", "level": "INFO", "message": "hello", "created_at": "2026-03-08T00:00:00Z"}]
        return {
            "run": self.get_run(run_id),
            "stages": [],
            "progress": [],
            "logs": logs,
        }


def test_start_run_command_accepted(monkeypatch) -> None:
    monkeypatch.setattr(api, "ControlRepository", ApiRepo)
    monkeypatch.setattr(api, "ControlOrchestrator", DummyOrchestrator)
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/runs", json={"pipeline_type": "full_pipeline", "target_scope": "all", "options": {}})

    assert response.status_code == 202
    assert response.json()["command_id"] == 7


def test_logs_endpoint_returns_ascending_ids(monkeypatch) -> None:
    monkeypatch.setattr(api, "ControlRepository", ApiRepo)
    monkeypatch.setattr(api, "ControlOrchestrator", DummyOrchestrator)
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/runs/1/logs")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [1, 2]


def test_sse_events_emit_db_snapshot_updates(monkeypatch) -> None:
    monkeypatch.setattr(api, "ControlRepository", ApiRepo)
    monkeypatch.setattr(api, "ControlOrchestrator", DummyOrchestrator)
    app = create_app()
    client = TestClient(app)

    with client.stream("GET", "/api/runs/1/events") as response:
        assert response.status_code == 200
        collected: list[str] = []
        for line in response.iter_lines():
            if line:
                collected.append(line)
            if len(collected) > 6:
                break

    payload = "\n".join(collected)
    assert "event: log" in payload
    assert "hello" in payload
