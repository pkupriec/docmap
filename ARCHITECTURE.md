# Architecture

## System Context

DocMap is a batch-oriented pipeline with an integrated operator control plane.

Primary flow:

`SCP Wiki -> Crawler -> Snapshots -> Extractor -> Geocoder -> Analytics -> BigQuery`

Control flow:

`UI/REST -> pipeline_commands -> orchestrator -> pipeline_runs/stages/progress/logs`

## Components

### Application Runtime (`implemented`)

- FastAPI app created in `services/control/api.py:create_app`
- Startup:
  - logging setup
  - startup migrations (`run_startup_migrations`)
  - orchestrator thread start

### Data Plane Services (`implemented`)

- `crawler`: fetch + parse + snapshot persistence
- `extractor`: prompt build, LLM call, validation, mention persistence
  - extractor runtime knobs: `EXTRACTOR_MODEL`, `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_THINK_LEVEL`, `OLLAMA_NUM_PREDICT`
- `geocoder`: resolve normalized names, cache, link documents
- `analytics`: rebuild BI tables
- `bigquery_exporter`: export BI tables to BigQuery

### Control Plane (`implemented`)

- REST command/monitoring API under `/api`
- SSE endpoint `/api/runs/{run_id}/events`
- command queue table `pipeline_commands`
- live status tables: `pipeline_runs`, `pipeline_stage_runs`, `pipeline_progress`, `pipeline_logs`

## Concurrency Model

- `implemented`: exactly one active run at a time
- `implemented`: one command worker loop (orchestrator thread)
- `partial`: long-running stage preemption is cooperative at item boundaries (crawl/extract/geocode)

## Stage Resume Model

- `implemented`: resume endpoint exists and reuses `retry_stage` command with `payload_json.resume=true`
- `implemented`: resume offset uses `pipeline_progress.current_index`
- `partial`: resume precision depends on stage semantics (best-effort in batched stages)

## Failure Model

- `implemented`: item-level failures are logged and do not always abort the entire stage
- `implemented`: fatal stage exceptions mark stage/run failed
- `implemented`: cancel requests are soft and applied at boundaries
- `partial`: operational robustness around external outages depends on environment reliability

## Deployment Model

- `implemented`: local Docker Compose topology:
  - `postgres`
  - `app`
  - `control-ui`
  - `pgadmin`
- `planned`: production deployment topology and hardening are not codified yet
