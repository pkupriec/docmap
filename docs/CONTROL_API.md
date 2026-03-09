# Control API

This document reflects the API implemented in `services/control/api.py`.

Base path: `/api`

## Status

- `implemented`: run listing/details/progress/logs
- `implemented`: command enqueue endpoints
- `implemented`: SSE stream for live updates
- `partial`: no auth/authz layer

## Endpoints

### Runs

- `GET /runs`
  - query: `limit`, `status`, `pipeline_type`
- `POST /runs`
  - body: `StartRunRequest`
  - enqueues `start_run`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/stages`
- `GET /runs/{run_id}/progress`
- `GET /runs/{run_id}/logs`
  - query: `after_id`, `limit`, `level`, `stage_name`, `service_name`

### Commands (mutations)

- `POST /runs/{run_id}/cancel`
  - enqueues `cancel_run`
- `POST /runs/{run_id}/retry`
  - enqueues `retry_run`
- `POST /runs/{run_id}/stages/{stage_name}/retry`
  - enqueues `retry_stage`
- `POST /runs/{run_id}/stages/{stage_name}/resume`
  - enqueues `retry_stage` with `payload_json={"resume": true}`
- `GET /commands/{command_id}`

### Streaming

- `GET /runs/{run_id}/events`
  - SSE events:
    - `run_status`
    - `stage_status`
    - `progress`
    - `log`
    - `heartbeat`

## Command Processing Notes

- API writes commands only; orchestrator applies them.
- Duplicate pending `start_run` is rejected with 409.
- Single-active-run policy is enforced by orchestrator behavior.

## Response Models

Defined in `services/control/schemas.py`:
- `StartRunRequest`
- `RetryRunRequest`
- `CommandAcceptedResponse`
- read models for runs/stages/progress/logs/commands

## Error Pattern

Typical error payload:

```json
{"error": "<code>", "detail": "<message>"}
```

## OpenAPI Artifact

- `docs/CONTROL_API.openapi.yaml` exists but may lag implementation details.
- Current source of truth for behavior is `services/control/api.py` + repository/orchestrator logic.
