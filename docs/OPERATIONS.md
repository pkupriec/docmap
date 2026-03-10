# Operations Runbook

## Service Endpoints

- API: `http://localhost:8000`
- UI: `http://localhost:5173`
- pgAdmin: `http://localhost:5050`

## Start / Stop

Start:
`docker compose -f infra/docker-compose.yml up -d --build`

Stop:
`docker compose -f infra/docker-compose.yml down`

Restart app only:
`docker compose -f infra/docker-compose.yml restart app`

## Health Checks

- Container status:
  `docker compose -f infra/docker-compose.yml ps`
- Tail app logs:
  `docker compose -f infra/docker-compose.yml logs --tail=200 app`

## Control API Operations

### Start run
`POST /api/runs`

### Cancel run
`POST /api/runs/{run_id}/cancel`

### Retry run
`POST /api/runs/{run_id}/retry`

### Retry stage
`POST /api/runs/{run_id}/stages/{stage_name}/retry`

### Resume stage
`POST /api/runs/{run_id}/stages/{stage_name}/resume`

### Observe
- run details: `GET /api/runs/{run_id}`
- logs: `GET /api/runs/{run_id}/logs`
- stream: `GET /api/runs/{run_id}/events`

## Frequent Failure Cases

### BigQuery export fails (`GCP_PROJECT_ID is required`)

Cause: missing export env/credentials.

Action:
- set `GCP_PROJECT_ID`
- verify `BIGQUERY_DATASET`/`BIGQUERY_LOCATION`
- ensure credentials file mounted and valid

### UI API proxy errors (`ECONNRESET`/`ECONNREFUSED`)

Cause: app restart/crash during Vite proxy request.

Action:
- check `app` container status/logs
- refresh UI after app recovery

### Command seems stuck

Action:
- check `pipeline_commands` status via API (`GET /api/commands/{id}`)
- inspect active run state in UI
- if needed, restart `app` and recheck command transitions

### Extraction is very slow or hits Ollama timeouts

Cause: long LLM generation time for selected model/prompt complexity.

Action:
- check extractor/Ollama timing logs in app output (`extractor.ollama_request_success` fields)
- tune extractor env vars:
  - `EXTRACTOR_MODEL` (for example `gpt-oss:20b` for higher throughput)
  - `OLLAMA_THINK_LEVEL` (default `low`)
  - `OLLAMA_TIMEOUT_SECONDS` (increase only if needed)
  - `OLLAMA_NUM_PREDICT` (optional output cap)
- restart app container after env changes:
  `docker compose -f infra/docker-compose.yml restart app`

### Geocoder shows many unresolved or 429 responses

Cause: public Nominatim rate limiting and/or overly specific location strings.

Action:
- verify geocoder env settings:
  - `GEOCODER_MIN_INTERVAL_SECONDS`
  - `GEOCODER_USER_AGENT`
  - `GEOCODER_URL`
- inspect geocoder logs for:
  - `geocoder.nominatim_rate_limited`
  - `geocoder.nominatim_not_found`
  - fallback query behavior (`query=...`)
- note geocode progress semantics:
  - `total_items` reflects backlog context
  - stage may still process only configured per-run limit

## Data Safety Notes

- `implemented`: control logs are pruned to last 10 runs
- `partial`: no automated backup/restore workflow in repository
- `planned`: operational backup policy and disaster recovery guide
