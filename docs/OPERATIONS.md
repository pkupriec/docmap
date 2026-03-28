# Operations Runbook

## Service Endpoints

- API: `http://localhost:8000`
- Control UI: `http://localhost:5173`
- Presentation UI/API: `http://localhost:8080`
- pgAdmin: `http://localhost:5050`

## Start / Stop

Start:
`docker compose -f infra/docker-compose.yml up -d --build`

Stop:
`docker compose -f infra/docker-compose.yml down`

Restart app only:
`docker compose -f infra/docker-compose.yml restart app`

Restart presentation only:
`docker compose -f infra/docker-compose.yml restart presentation`

## Health Checks

- Container status:
  `docker compose -f infra/docker-compose.yml ps`
- Tail app logs:
  `docker compose -f infra/docker-compose.yml logs --tail=200 app`
- Tail presentation logs:
  `docker compose -f infra/docker-compose.yml logs --tail=200 presentation`

## Presentation API Operations

- `GET /api/map/locations`
- `GET /api/map/location/{location_id}/documents`
- `GET /api/map/document/{document_id}/locations`
- `GET /api/map/overlays/density`
- `GET /healthz`

## Canonical Dictionary Refresh (Phase 16)

Canonical dictionary refresh is controlled per run from Control UI:
- Start Run -> select `full_pipeline` or `geocode_only`
- enable checkbox: `Reload canonical dictionary before geocoding`

When enabled, geocode stage refreshes canonical tables at stage start (index `0`) before normalization/geocoding.

One-shot refresh via compose profile:
`docker compose -f infra/docker-compose.yml --profile offline-tools run --rm canonical-refresh`

Manual refresh from app container:
`docker compose -f infra/docker-compose.yml run --rm app sh -lc "python -m services.geocoder.scripts.refresh_canonical_dictionary --input \"$CANONICAL_DICTIONARY_INPUT\" --source \"$CANONICAL_DICTIONARY_SOURCE\" --report \"$CANONICAL_REFRESH_REPORT_PATH\" --replace-source"`

Expected outputs:
- canonical tables populated/updated: `geo_canonical_places`, `geo_canonical_aliases`, `geo_canonical_concordances`
- deterministic JSON report at `CANONICAL_REFRESH_REPORT_PATH` with counts and safe-alias collision diagnostics

Controls:
- `CANONICAL_REFRESH_ON_GEOCODE=1|0` (default `0`, used as fallback when run option is not provided)
- `CANONICAL_DICTIONARY_INPUT` (default `/app/services/geocoder/assets/canonical_dictionary.json`)
- `CANONICAL_DICTIONARY_SOURCE` (default `wof`)
- `CANONICAL_REFRESH_REPLACE_SOURCE=1|0` (default `1`)
- `CANONICAL_AUTOSEED_ON_EMPTY=1|0` (default `1`; generate initial dictionary when input is missing/empty)
- `CANONICAL_BUILD_SEED_SOURCE_ON_REFRESH=1|0` (default `1`; geocoder builds seed source when missing/empty)
- `CANONICAL_SEED_SOURCE` (default `/app/services/geocoder/assets/canonical_seed_source.geojson`)

Seed generation semantics:
- canonical name comes from source `location_name`
- safe aliases come from `safe_aliases`/`aliases`
- unsafe aliases come from `unsafe_aliases` and are tagged `unsafe_parent_ref`
- canonical IDs come from source `canonical_id` (fallback `seed:<rank>:<normalized_name>`)

Ownership note:
- geocoder seed source and canonical dictionary refresh are geocoder-owned
- analytics artifacts are not required by geocode stage for canonical seeding

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
