# Architecture

## System Flows

Data flow:
`SCP Wiki -> crawl -> snapshots -> extract -> geocode -> analytics -> export`

Control flow:
`UI/API -> pipeline_commands -> orchestrator -> runs/stages/progress/logs`

Presentation flow:
`BI tables -> presentation API -> presentation UI`

## Runtime Components

Control runtime:
- app factory: `services/control/api.py:create_app`
- orchestrator: `services/control/orchestrator.py`

Presentation runtime:
- app factory: `services/presentation/backend/api.py:create_presentation_app`
- API and static frontend served from `presentation` container

Shared infrastructure:
- DB and schema startup: `services/common/*`, `database/*.sql`
- local deployment: `infra/docker-compose.yml`

## Concurrency and Execution Model

- Single active run policy enforced by orchestrator and control repository logic.
- Commands are queued in `pipeline_commands` and applied asynchronously.
- Cancellation is cooperative at item/stage boundaries.
- Resume is stage-level and uses saved progress indexes.

## Failure Model

- Item-level failures are logged and can be isolated per stage implementation.
- Fatal stage exception marks stage and run as failed.
- SSE stream exposes live `run_status`, `stage_status`, `progress`, `log`, `heartbeat` events.

## Canonical Geo Identity Model

- Geocoder can refresh canonical dictionary before geocoding stage.
- `geo_locations` stores canonical linkage fields:
  - `canonical_id`
  - `canonical_resolution_method`
  - `canonical_confidence`
  - `canonical_resolution_details`
- Ambiguous safe-alias matches are resolved by deterministic scoring logic.

## Deployment Model

Local compose services:
- `postgres`
- `app`
- `control-ui`
- `presentation`
- `canonical-refresh` (profile `offline-tools`)
- `pgadmin`