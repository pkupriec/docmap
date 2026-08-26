from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from services.control.constants import PIPELINE_TYPES, TARGET_SCOPES
from services.control.repository import ControlRepository


@dataclass(frozen=True)
class QueuedPipelineRun:
    command_id: int
    status: str = "pending"


class PipelineCommandService:
    """The single write entrypoint for starting pipeline work.

    This service only enqueues commands. Stage execution belongs exclusively to
    ``ControlOrchestrator`` so API and scheduled runs share the same lifecycle,
    progress, retry, and cancellation behavior.
    """

    def __init__(self, repository: ControlRepository | None = None) -> None:
        self.repository = repository or ControlRepository()

    def enqueue_run(
        self,
        *,
        pipeline_type: str,
        target_scope: str,
        document_url: str | None = None,
        document_range: dict[str, int] | None = None,
        options: dict[str, Any] | None = None,
        requested_by: str | None = None,
    ) -> QueuedPipelineRun:
        if pipeline_type not in PIPELINE_TYPES:
            raise ValueError(f"invalid pipeline_type: {pipeline_type}")
        if target_scope not in TARGET_SCOPES:
            raise ValueError(f"invalid target_scope: {target_scope}")

        payload = {
            "pipeline_type": pipeline_type,
            "target_scope": target_scope,
            "document_url": document_url,
            "document_range": document_range,
            "options": dict(options or {}),
        }
        dedupe_key = f"start_run:{json.dumps(payload, sort_keys=True)}"
        command_id = self.repository.enqueue_command(
            "start_run",
            payload_json=payload,
            requested_by=requested_by,
            dedupe_key=dedupe_key,
        )
        return QueuedPipelineRun(command_id=command_id)

    def enqueue_incremental_run(self, *, requested_by: str = "scheduler") -> QueuedPipelineRun:
        return self.enqueue_run(
            pipeline_type="full_pipeline",
            target_scope="incremental",
            options={"process_unprocessed_only": True},
            requested_by=requested_by,
        )
