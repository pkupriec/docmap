from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, FastAPI, Query
from fastapi.responses import JSONResponse, StreamingResponse

from services.common.logging import configure_logging
from services.common.migrations import run_startup_migrations
from services.control.constants import PIPELINE_TYPES, TARGET_SCOPES
from services.control.orchestrator import ControlOrchestrator
from services.control.repository import ControlRepository, DuplicatePendingCommandError
from services.control.schemas import (
    CommandAcceptedResponse,
    RetryRunRequest,
    StartRunRequest,
)


router = APIRouter(prefix="/api")


def _normalize_datetimes(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _error_response(status_code: int, error: str, detail: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error, "detail": detail})


@router.get("/runs")
def list_runs(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = None,
    pipeline_type: str | None = None,
) -> dict[str, Any]:
    repo = ControlRepository()
    items = repo.list_runs(limit=limit, status=status, pipeline_type=pipeline_type)
    return {"items": [_normalize_datetimes(item) for item in items]}


@router.post("/runs", status_code=202, response_model=CommandAcceptedResponse)
def start_run(request: StartRunRequest) -> CommandAcceptedResponse:
    if request.pipeline_type not in PIPELINE_TYPES:
        return _error_response(409, "invalid_request", "invalid pipeline_type")
    if request.target_scope not in TARGET_SCOPES:
        return _error_response(409, "invalid_request", "invalid target_scope")

    payload = request.model_dump()
    dedupe_key = f"start_run:{json.dumps(payload, sort_keys=True)}"

    repo = ControlRepository()
    try:
        command_id = repo.enqueue_command(
            "start_run",
            payload_json=payload,
            dedupe_key=dedupe_key,
        )
    except DuplicatePendingCommandError:
        return _error_response(409, "duplicate_command", "duplicate pending start_run command")

    return CommandAcceptedResponse(command_id=command_id, status="pending")


@router.get("/runs/{run_id}")
def get_run(run_id: int) -> dict[str, Any]:
    repo = ControlRepository()
    run = repo.get_run(run_id)
    if not run:
        return _error_response(404, "not_found", "run not found")
    return {
        "run": _normalize_datetimes(run),
        "stages": [_normalize_datetimes(row) for row in repo.list_stages(run_id)],
        "progress": [_normalize_datetimes(row) for row in repo.list_progress(run_id)],
    }


@router.get("/runs/{run_id}/stages")
def get_stages(run_id: int) -> dict[str, Any]:
    repo = ControlRepository()
    run = repo.get_run(run_id)
    if not run:
        return _error_response(404, "not_found", "run not found")
    return {"items": [_normalize_datetimes(row) for row in repo.list_stages(run_id)]}


@router.get("/runs/{run_id}/progress")
def get_progress(run_id: int) -> dict[str, Any]:
    repo = ControlRepository()
    run = repo.get_run(run_id)
    if not run:
        return _error_response(404, "not_found", "run not found")
    return {"items": [_normalize_datetimes(row) for row in repo.list_progress(run_id)]}


@router.get("/runs/{run_id}/logs")
def get_logs(
    run_id: int,
    after_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=200, ge=1, le=1000),
    level: str | None = None,
    stage_name: str | None = None,
    service_name: str | None = None,
) -> dict[str, Any]:
    repo = ControlRepository()
    run = repo.get_run(run_id)
    if not run:
        return _error_response(404, "not_found", "run not found")

    items = repo.list_logs(
        run_id,
        after_id=after_id,
        limit=limit,
        level=level,
        stage_name=stage_name,
        service_name=service_name,
    )
    return {"items": [_normalize_datetimes(row) for row in items]}


@router.post("/runs/{run_id}/cancel", status_code=202, response_model=CommandAcceptedResponse)
def cancel_run(run_id: int) -> CommandAcceptedResponse:
    repo = ControlRepository()
    if not repo.run_exists(run_id):
        return _error_response(404, "not_found", "run not found")
    command_id = repo.enqueue_command("cancel_run", pipeline_run_id=run_id)
    return CommandAcceptedResponse(command_id=command_id, status="pending")


@router.post("/runs/{run_id}/retry", status_code=202, response_model=CommandAcceptedResponse)
def retry_run(run_id: int, request: RetryRunRequest | None = None) -> CommandAcceptedResponse:
    repo = ControlRepository()
    if not repo.run_exists(run_id):
        return _error_response(404, "not_found", "run not found")
    payload = request.model_dump() if request else {}
    command_id = repo.enqueue_command("retry_run", pipeline_run_id=run_id, payload_json=payload)
    return CommandAcceptedResponse(command_id=command_id, status="pending")


@router.post("/runs/{run_id}/stages/{stage_name}/retry", status_code=202, response_model=CommandAcceptedResponse)
def retry_stage(run_id: int, stage_name: str) -> CommandAcceptedResponse:
    repo = ControlRepository()
    if not repo.run_exists(run_id) or not repo.stage_exists(run_id, stage_name):
        return _error_response(404, "not_found", "run or stage not found")
    command_id = repo.enqueue_command("retry_stage", pipeline_run_id=run_id, stage_name=stage_name)
    return CommandAcceptedResponse(command_id=command_id, status="pending")


@router.post("/runs/{run_id}/stages/{stage_name}/resume", status_code=202, response_model=CommandAcceptedResponse)
def resume_stage(run_id: int, stage_name: str) -> CommandAcceptedResponse:
    repo = ControlRepository()
    if not repo.run_exists(run_id) or not repo.stage_exists(run_id, stage_name):
        return _error_response(404, "not_found", "run or stage not found")
    command_id = repo.enqueue_command(
        "retry_stage",
        pipeline_run_id=run_id,
        stage_name=stage_name,
        payload_json={"resume": True},
    )
    return CommandAcceptedResponse(command_id=command_id, status="pending")


@router.get("/commands/{command_id}")
def get_command(command_id: int) -> dict[str, Any]:
    repo = ControlRepository()
    command = repo.get_command(command_id)
    if not command:
        return _error_response(404, "not_found", "command not found")
    return _normalize_datetimes(command)


def _sse_event(event_name: str, event_id: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, default=str)
    return f"id: {event_id}\nevent: {event_name}\ndata: {body}\n\n"


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: int, last_event_id: str | None = None) -> StreamingResponse:
    repo = ControlRepository()
    if not repo.run_exists(run_id):
        return _error_response(404, "not_found", "run not found")

    after_log_id = 0
    if last_event_id:
        try:
            after_log_id = int(last_event_id)
        except ValueError:
            after_log_id = 0

    async def generator():
        nonlocal after_log_id
        while True:
            snapshot = repo.get_latest_state_snapshot(run_id, after_log_id=after_log_id)
            run = _normalize_datetimes(snapshot["run"])
            yield _sse_event("run_status", f"run-{run['id']}-{run['updated_at']}", run)

            for stage in snapshot["stages"]:
                item = _normalize_datetimes(stage)
                yield _sse_event("stage_status", f"stage-{item['id']}-{item['updated_at']}", item)

            for progress_row in snapshot["progress"]:
                item = _normalize_datetimes(progress_row)
                yield _sse_event(
                    "progress",
                    f"progress-{item['pipeline_run_id']}-{item['stage_name']}-{item['updated_at']}",
                    item,
                )

            for log_row in snapshot["logs"]:
                item = _normalize_datetimes(log_row)
                after_log_id = max(after_log_id, int(item["id"]))
                yield _sse_event("log", str(item["id"]), item)

            yield _sse_event("heartbeat", f"hb-{int(asyncio.get_running_loop().time())}", {"run_id": run_id})
            await asyncio.sleep(1)

    return StreamingResponse(generator(), media_type="text/event-stream")


def create_app() -> FastAPI:
    app = FastAPI(title="DocMap Control API", version="1.0.0")
    app.include_router(router)

    orchestrator = ControlOrchestrator()

    @app.on_event("startup")
    def _startup() -> None:
        configure_logging()
        run_startup_migrations()
        orchestrator.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        orchestrator.stop()

    return app
