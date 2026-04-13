# Checkpoint 1 Summary (Control Backend Contracts)

Date: 2026-03-28

## Scope Reviewed

Code:
- `services/control/api.py`
- `services/control/orchestrator.py`
- `services/control/repository.py`
- `services/control/constants.py`
- `services/control/schemas.py`
- `database/control_plane.sql`
- `tests/test_control_api.py`
- `tests/test_control_orchestrator.py`

Docs:
- `docs/api/CONTROL_API.md`
- `docs/api/CONTROL_API.openapi.yaml`
- `docs/operations/OPERATIONS.md` (validation only)
- `docs/architecture/PIPELINE.md` (validation only)
- `docs/architecture/SERVICES.md` (validation only)

## Alignment Outcome

Checkpoint 1 performed control contract alignment in docs and kept code unchanged.

Updated docs:
- `docs/api/CONTROL_API.md`
- `docs/api/CONTROL_API.openapi.yaml`

## Behavior Facts Locked

- `POST /api/runs` validates `pipeline_type` and `target_scope`; invalid values return `409 invalid_request`.
- duplicate pending start command returns `409 duplicate_command` (dedupe by pending `dedupe_key`).
- `POST /api/runs/{run_id}/retry` accepts optional `{ "options": { ... } }` and creates a new run from the target run.
- if another run is active, start/retry/retry-stage commands are deferred and active run is moved to `cancelling`.
- `GET /api/runs/{run_id}/events` uses `last_event_id` as numeric log cursor; non-integer values are treated as `0`.
- SSE emits synthetic ids for run/stage/progress/heartbeat and numeric ids for log events.

## Ready For

Checkpoint 2: presentation backend contract extraction and docs alignment.
