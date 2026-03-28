# Operations Runbook

## Local Endpoints

- Control API: `http://localhost:8000`
- Control UI: `http://localhost:5173`
- Presentation runtime: `http://localhost:8080`
- pgAdmin: `http://localhost:5050`

## Compose Lifecycle

Start:
`docker compose -f infra/docker-compose.yml up -d --build`

Stop:
`docker compose -f infra/docker-compose.yml down`

## Health and Logs

- `docker compose -f infra/docker-compose.yml ps`
- `docker compose -f infra/docker-compose.yml logs --tail=200 app`
- `docker compose -f infra/docker-compose.yml logs --tail=200 presentation`

## Control API Operations

- `POST /api/runs`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/runs/{run_id}/retry`
- `POST /api/runs/{run_id}/stages/{stage_name}/retry`
- `POST /api/runs/{run_id}/stages/{stage_name}/resume`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/logs`
- `GET /api/runs/{run_id}/events`

## Presentation API Operations

- `GET /api/map/locations`
- `GET /api/map/boundaries`
- `GET /api/map/location/{location_id}/documents`
- `GET /api/map/document/{document_id}`
- `GET /api/map/document/{document_id}/pdf`
- `GET /api/map/document/{document_id}/locations`
- `GET /api/map/overlays/density`
- `GET /api/search`
- `GET /healthz`

## Canonical Dictionary Refresh

One-shot via offline profile:
`docker compose -f infra/docker-compose.yml --profile offline-tools run --rm canonical-refresh`

Manual from app image:
`docker compose -f infra/docker-compose.yml run --rm app sh -lc "python -m services.geocoder.scripts.refresh_canonical_dictionary --input \"$CANONICAL_DICTIONARY_INPUT\" --source \"$CANONICAL_DICTIONARY_SOURCE\" --report \"$CANONICAL_REFRESH_REPORT_PATH\" --replace-source"`

Expected outputs:
- canonical tables updated
- refresh report JSON at configured report path

## Common Failure Cases

- BigQuery export fails: missing project/credentials config.
- UI proxy errors: app restarting or unavailable.
- Long geocode runs: review rate limits and geocoder env tuning.
- Stuck commands: inspect `/api/commands/{command_id}` and active run state.