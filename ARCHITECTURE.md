# Architecture

## System Context

DocMap is a batch-oriented pipeline with an integrated operator control plane.

Primary data flow:

`SCP Wiki -> Crawler -> Snapshots -> Extractor -> Geocoder -> Analytics -> BI tables -> BigQuery`

Control flow:

`UI/REST -> pipeline_commands -> orchestrator -> pipeline_runs/stages/progress/logs`

Presentation flow:

`BI tables -> presentation API -> presentation UI -> interactive spatial exploration`

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

### Presentation Layer (`implemented`)

- read-only presentation API over BI tables
- interactive spatial UI for document/location exploration
- map-first interface using location points and document links
- does not write to operational or BI tables
- does not perform extraction, normalization, or geocoding
- `partial`: current mixed geometry support relies on sparse static assets and fragile display-name matching
- `planned`: phase 13 extends presentation rendering to reliable real geometry for `admin_region`, `country`, `continent`, and `ocean` while preserving `city` points

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

## Transaction Pattern

- `implemented`: services should commit by atomic unit of work where practical.
- Current pattern:
  - extractor commits per snapshot
  - geocoder commits per mention
- rationale: improve durability/observability during long-running stages and limit rollback scope on single-item failures

## Deployment Model

- `implemented`: local Docker Compose topology:
  - `postgres`
  - `app`
  - `control-ui`
  - `presentation`
  - `pgadmin`
- `planned`: production deployment topology and hardening are not codified yet
- `implemented`: dedicated presentation service/container (`Dockerfile.presentation`, `main_presentation.py`)

## Geometry Asset Model

- `implemented`: analytics owns static geometry asset generation for presentation runtime consumption
- `implemented`: presentation runtime consumes prebuilt geometry assets read-only
- `partial`: current asset coverage is insufficient for broad real-geometry rendering
- `planned`: phase 13 introduces stable geometry matching keyed by location identity rather than display-name string matching
- `planned`: hierarchy fallback remains `city -> region -> country`; `continent` and `ocean` are rendering ranks only
