# Pipeline Behavior

## Stage Order

For `full_pipeline`:
1. `crawl`
2. `extract`
3. `geocode`
4. `analytics`
5. `export`

## Pipeline Types

Defined in `services/control/constants.py`:
- `full_pipeline`
- `crawl_only`
- `extract_only`
- `geocode_only`
- `analytics_only`
- `export_only`

## Target Scopes

Supported scopes:
- `all`
- `single_document`
- `document_range`
- `incremental`

## Command Model

Command types:
- `start_run`
- `cancel_run`
- `retry_run`
- `retry_stage`

Resume stage is implemented as `retry_stage` with payload `{ "resume": true }`.

## Run Options in Current Code

`StartRunRequest.options` is an open object. Current orchestrator behavior uses:
- `process_unprocessed_only`
- `refresh_canonical_dictionary`
- `refresh_geo_identity`

Notable semantics:
- `refresh_canonical_dictionary` controls canonical table refresh at geocode stage start.
- `refresh_geo_identity` enables re-geocoding cache entries missing rank/OSM/bbox/canonical identity.
- if `refresh_geo_identity` is used in full geocode mode, orchestrator auto-enqueues follow-up `analytics_only` run.

## Resume and Retry Semantics

- Retry stage resets selected stage and downstream state.
- Resume stage preserves saved progress index when valid.
- If resume index is exhausted, system falls back to full stage retry.

## Scheduler

- Scheduler module exists: `services/pipeline/scheduler.py`.
- It is not auto-started by `main.py` in current stack.

## Observability

- persistent logs: `pipeline_logs`
- progress cursors: `pipeline_progress`
- SSE endpoint: `/api/runs/{run_id}/events`