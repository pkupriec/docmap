from __future__ import annotations

from services.control.repository import DuplicatePendingCommandError
from services.pipeline import scheduler
from services.pipeline.service import QueuedPipelineRun


class FakeCommandService:
    def __init__(self, failures: int = 0) -> None:
        self.calls = 0
        self.failures = failures

    def enqueue_incremental_run(self) -> QueuedPipelineRun:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("temporary database failure")
        return QueuedPipelineRun(command_id=23)


def test_run_scheduled_incremental_job_enqueues_control_command() -> None:
    service = FakeCommandService()

    scheduler.run_scheduled_incremental_job(max_retries=1, command_service=service)

    assert service.calls == 1


def test_run_scheduled_incremental_job_retries_enqueue(monkeypatch) -> None:
    service = FakeCommandService(failures=1)
    monkeypatch.setattr(scheduler.time, "sleep", lambda _: None)

    scheduler.run_scheduled_incremental_job(max_retries=2, command_service=service)

    assert service.calls == 2


def test_run_scheduled_incremental_job_skips_duplicate_pending_command() -> None:
    class DuplicateService:
        def enqueue_incremental_run(self):
            raise DuplicatePendingCommandError()

    scheduler.run_scheduled_incremental_job(command_service=DuplicateService())
