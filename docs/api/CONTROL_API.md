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

## Streaming

`GET /runs/{run_id}/events` emits:
- `run_status`
- `stage_status`
- `progress`
- `log`
- `heartbeat`

## Error Payload

```json
{"error": "<code>", "detail": "<message>"}
```

## Notes

- API enqueues commands; orchestrator applies state transitions.
- Duplicate pending `start_run` requests are rejected (`409`).
- Single-active-run policy is enforced by runtime logic.
- OpenAPI artifact: `docs/api/CONTROL_API.openapi.yaml`.
