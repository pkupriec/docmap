from __future__ import annotations

import logging
import os
import threading
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from services.common.logging import configure_logging
from services.control.repository import DuplicatePendingCommandError
from services.pipeline.service import PipelineCommandService


logger = logging.getLogger(__name__)
_RUN_LOCK = threading.Lock()


def run_scheduled_incremental_job(
    max_retries: int = 2,
    *,
    command_service: PipelineCommandService | None = None,
) -> None:
    if not _RUN_LOCK.acquire(blocking=False):
        logger.warning("scheduler.skip_overlapping_run")
        return

    started_at = time.time()
    logger.info("scheduler.enqueue_start")
    service = command_service or PipelineCommandService()

    try:
        for attempt in range(1, max_retries + 2):
            try:
                result = service.enqueue_incremental_run()
                logger.info(
                    "scheduler.enqueue_success command_id=%s attempt=%s",
                    result.command_id,
                    attempt,
                )
                return
            except DuplicatePendingCommandError:
                logger.info("scheduler.enqueue_skipped reason=duplicate_pending_command")
                return
            except Exception:
                logger.exception(
                    "scheduler.enqueue_attempt_failed attempt=%s",
                    attempt,
                )
                if attempt > max_retries:
                    raise
                time.sleep(2 ** (attempt - 1))
    finally:
        duration = round(time.time() - started_at, 2)
        logger.info("scheduler.enqueue_end duration_seconds=%s", duration)
        _RUN_LOCK.release()


def start_scheduler() -> None:
    configure_logging()
    cron_expr = os.getenv("SCHEDULER_CRON", "0 3 * * 1")
    timezone = os.getenv("SCHEDULER_TIMEZONE", "UTC")
    max_retries = int(os.getenv("SCHEDULER_MAX_RETRIES", "2"))

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        lambda: run_scheduled_incremental_job(max_retries=max_retries),
        trigger=CronTrigger.from_crontab(cron_expr, timezone=timezone),
        id="weekly_incremental",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    logger.info("scheduler.started cron=%s timezone=%s", cron_expr, timezone)
    scheduler.start()
