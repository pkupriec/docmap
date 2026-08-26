from __future__ import annotations

import pytest

from services.pipeline.service import PipelineCommandService


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def enqueue_command(self, command_type: str, **kwargs) -> int:
        self.calls.append((command_type, kwargs))
        return 17


def test_enqueue_run_builds_canonical_start_command() -> None:
    repo = FakeRepository()
    service = PipelineCommandService(repo)

    queued = service.enqueue_run(
        pipeline_type="full_pipeline",
        target_scope="single_document",
        document_url="https://example.test/scp-001",
        options={"process_unprocessed_only": False},
        requested_by="test",
    )

    assert queued.command_id == 17
    command_type, kwargs = repo.calls[0]
    assert command_type == "start_run"
    assert kwargs["payload_json"]["options"] == {"process_unprocessed_only": False}
    assert kwargs["requested_by"] == "test"
    assert kwargs["dedupe_key"].startswith("start_run:")


def test_enqueue_incremental_run_uses_control_plane_semantics() -> None:
    repo = FakeRepository()

    PipelineCommandService(repo).enqueue_incremental_run()

    _, kwargs = repo.calls[0]
    assert kwargs["payload_json"] == {
        "pipeline_type": "full_pipeline",
        "target_scope": "incremental",
        "document_url": None,
        "document_range": None,
        "options": {"process_unprocessed_only": True},
    }
    assert kwargs["requested_by"] == "scheduler"


def test_enqueue_run_rejects_unknown_pipeline_type() -> None:
    with pytest.raises(ValueError, match="invalid pipeline_type"):
        PipelineCommandService(FakeRepository()).enqueue_run(
            pipeline_type="unknown",
            target_scope="all",
        )
