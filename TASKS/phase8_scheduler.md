# Phase 8 - Scheduler

Goal: automate weekly incremental pipeline execution.

## Scheduling Model

- Scheduler runs in the app container.
- Timezone is UTC unless explicitly configured.
- Use cron-compatible expressions.

## Tasks

1. Implement scheduler bootstrap.
2. Add weekly incremental pipeline job:
   - cron: `0 3 * * 1` (every Monday 03:00 UTC)
   - operation: `run_incremental_pipeline`
3. Add optional manual one-shot command for backfill/debug.
4. Implement job-level retry policy for transient failures (max 2 retries).
5. Persist run metadata in logs:
   - run_id
   - start/end timestamp
   - stage-level success/failure
6. Ensure overlapping runs are prevented (single-flight lock).

## Acceptance Criteria

- Scheduler triggers the incremental job on schedule.
- If a scheduled run is active, next trigger is skipped with warning log.
- Failed scheduled runs are visible from logs and can be rerun manually.
