# Pipeline Behavior

Coding agents should read `PIPELINE.summary.md` first and open this file when the task needs full stage and command details.

## Stage Order

For `full_pipeline`:

1. `crawl`
2. `extract`
3. `geocode`
4. `analytics`
5. `export`

Analytics stage includes BI rebuild and, in phase 12, generation of presentation static administrative geometry assets from BI-derived location targets.

Planned phase 13 extension:

- analytics geometry build expands to stable real-geometry assets for `admin_region`, `country`, `continent`, and `ocean`
- geometry assets remain analytics-owned and presentation-consumed

## Pipeline Types

Defined in `services/control/constants.py`:
- `full_pipeline`
- `crawl_only`
- `extract_only`
- `geocode_only`
- `analytics_only`
- `export_only`

## Run Targets

Supported target scopes (`implemented`):
- `all`
- `single_document`
- `document_range`
- `incremental` (accepted by API, interpreted by current logic as generic scope metadata)

## Control Commands

Command queue type is `retry_stage|retry_run|start_run|cancel_run`.

- `start_run` (`implemented`)
- `cancel_run` (`implemented`, soft cancel)
- `retry_run` (`implemented`, creates replacement run)
- `retry_stage` (`implemented`)
- stage `resume` (`implemented`) is encoded as `retry_stage` with `payload_json.resume=true`

## Resume Semantics

- `implemented`: stage resume keeps current stage progress and resets only downstream stages
- `implemented`: stage functions use `pipeline_progress.current_index` to continue from offset
- `partial`: offset semantics are best effort for dynamically changing input sets

## Limits and Throughput

- Stage execution is no longer globally capped by environment variable.
- Per-run behavior is controlled by pipeline type, scope, and stage-specific options (for example unprocessed-only mode and resume offsets).
- Extract stage LLM tuning vars:
  - `EXTRACTOR_MODEL` (default `gpt-oss:20b`)
  - `OLLAMA_TIMEOUT_SECONDS` (default `300`)
  - `OLLAMA_THINK_LEVEL` (default `low`)
  - `OLLAMA_NUM_PREDICT` (optional cap)

## Geocode Progress Semantics

- `implemented`: geocode stage targets full eligible backlog for the run mode.
- `implemented`: UI/API `total_items` for geocode reflects real pending backlog at stage start.
- `implemented`: normalization and geocoding follow the same run mode and resume semantics.

## Transaction Semantics

- `implemented`: extractor commits per snapshot (atomic item).
- `implemented`: geocoder commits per mention (atomic item).
- benefit: long runs persist progress incrementally and isolate failures to individual items.

## Scheduler

- Module `services/pipeline/scheduler.py` exists (`implemented`)
- It schedules `run_incremental_pipeline` using APScheduler cron
- `partial`: scheduler is not wired into app startup and does not run automatically in current compose

## Failure and Cancellation

- `implemented`: run cancel is cooperative; stage stops at item boundary where supported
- `implemented`: stage errors mark stage/run failed with message
- `implemented`: stale pending cancel commands can be rejected during stage retry/resume

## Observability

- `implemented`: persistent per-run logs in `pipeline_logs`
- `implemented`: current state in `pipeline_progress`
- `implemented`: SSE event stream (`run_status`, `stage_status`, `progress`, `log`, `heartbeat`)

## Presentation Consumption

- `implemented`: presentation service reads BI outputs (`bi_documents`, `bi_locations`, `bi_document_locations`, `bi_location_hierarchy`) in read-only mode.
- `extended in phase 12`: presentation frontend reads static administrative geometry assets generated during analytics; no runtime geometry generation is performed in presentation startup.
- `planned in phase 13`: presentation consumes higher-coverage geometry assets matched by stable location identity; document fallback still remains `city -> region -> country`
