# Control API

Source of truth: `services/control/api.py`.

Base path: `/api`

## Runs

- `GET /runs?limit=&status=&pipeline_type=`
- `POST /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/stages`
- `GET /runs/{run_id}/progress`
- `GET /runs/{run_id}/logs?after_id=&limit=&level=&stage_name=&service_name=`
- `GET /runs/{run_id}/events` (SSE)

## Commands

- `POST /runs/{run_id}/cancel`
- `POST /runs/{run_id}/retry`
- `POST /runs/{run_id}/stages/{stage_name}/retry`
- `POST /runs/{run_id}/stages/{stage_name}/resume`
- `GET /commands/{command_id}`

## Start Run Request

`POST /runs` body:
- `pipeline_type`
- `target_scope`
- optional `document_url`
- optional `document_range` (`start`, `end`)
- optional `options` object

Current orchestrator-recognized options include:
- `process_unprocessed_only`
- `refresh_canonical_dictionary` (defaults to `true` for geocode/full runs)
- `refresh_geo_identity` (defaults to `true` for geocode/full runs)
- `full_refresh_geo_information` (forces full cache re-geocode from scratch)

Validation notes:
- invalid `pipeline_type` or `target_scope` returns `409` with `{"error":"invalid_request","detail":"..."}`.
- duplicate pending `start_run` payload returns `409` with `{"error":"duplicate_command","detail":"..."}`.

Retry notes:
- `POST /runs/{run_id}/retry` accepts optional body `{ "options": { ... } }`.
- retry creates a new run using target run `pipeline_type` + `target_scope`; payload options are merged into new run parameters.

## Streaming

`GET /runs/{run_id}/events` emits:
- `run_status`
- `stage_status`
- `progress`
- `log`
- `heartbeat`

SSE notes:
- query param `last_event_id` is interpreted as a numeric log cursor (`pipeline_logs.id`); non-integer values are treated as `0`.
- `log` events use numeric ids from `pipeline_logs.id`.
- `run_status`, `stage_status`, `progress`, and `heartbeat` use synthetic event ids.
- stream interval is approximately 1 second.

## Error Payload

```json
{"error": "<code>", "detail": "<message>"}
```

## Notes

- API enqueues commands; orchestrator applies state transitions.
- Duplicate pending `start_run` requests are rejected (`409`).
- Single-active-run policy is enforced by runtime logic.
- When another run is active, start/retry/retry-stage commands are deferred and the active run is moved to `cancelling`.
- OpenAPI artifact: `docs/api/CONTROL_API.openapi.yaml`.
