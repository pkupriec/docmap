from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StartRunRequest(BaseModel):
    pipeline_type: str
    target_scope: str
    document_url: str | None = None
    document_range: dict[str, int] | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class RetryRunRequest(BaseModel):
    options: dict[str, Any] = Field(default_factory=dict)


class CommandAcceptedResponse(BaseModel):
    command_id: int
    status: str
    message: str | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class PipelineRun(BaseModel):
    id: int
    pipeline_type: str
    status: str
    current_stage_name: str | None = None
    target_scope: str
    parameters_json: dict[str, Any]
    requested_by: str | None = None
    replacement_for_run_id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class PipelineStageRun(BaseModel):
    id: int
    pipeline_run_id: int
    stage_name: str
    status: str
    stage_order: int
    items_total: int | None = None
    items_completed: int
    items_failed: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class PipelineProgress(BaseModel):
    pipeline_run_id: int
    stage_name: str
    current_index: int
    total_items: int | None = None
    items_completed: int
    items_failed: int
    current_document_id: int | None = None
    current_document_url: str | None = None
    current_item_label: str | None = None
    message: str | None = None
    updated_at: datetime


class PipelineLog(BaseModel):
    id: int
    pipeline_run_id: int
    stage_name: str | None = None
    service_name: str
    level: str
    event_type: str | None = None
    message: str
    document_id: int | None = None
    document_url: str | None = None
    current_index: int | None = None
    payload_json: dict[str, Any] | None = None
    created_at: datetime


class PipelineCommand(BaseModel):
    id: int
    command_type: str
    pipeline_run_id: int | None = None
    stage_name: str | None = None
    payload_json: dict[str, Any]
    status: str
    requested_by: str | None = None
    requested_at: datetime
    processed_at: datetime | None = None
    error_message: str | None = None


class PipelineRunDetail(BaseModel):
    run: PipelineRun
    stages: list[PipelineStageRun]
    progress: list[PipelineProgress]
