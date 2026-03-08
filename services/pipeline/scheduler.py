from __future__ import annotations

import logging
import os
import threading
import time
import uuid

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from services.common.logging import configure_logging
from services.pipeline.service import run_incremental_pipeline


logger = logging.getLogger(__name__)
_RUN_LOCK = threading.Lock()


def run_scheduled_incremental_job(max_retries: int = 2) -> None:
    if not _RUN_LOCK.acquire(blocking=False):
        logger.warning("scheduler.skip_overlapping_run")
        return

    run_id = str(uuid.uuid4())
    started_at = time.time()
    logger.info("scheduler.run_start run_id=%s", run_id)

    try:
        for attempt in range(1, max_retries + 2):
            try:
                result = run_incremental_pipeline()
                logger.info(
                    "scheduler.run_success run_id=%s attempt=%s result=%s",
                    run_id,
                    attempt,
                    result,
                )
                return
            except Exception:
                logger.exception(
                    "scheduler.run_attempt_failed run_id=%s attempt=%s",
                    run_id,
                    attempt,
                )
                if attempt > max_retries:
                    raise
                time.sleep(2 ** (attempt - 1))
    finally:
        duration = round(time.time() - started_at, 2)
        logger.info("scheduler.run_end run_id=%s duration_seconds=%s", run_id, duration)
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
