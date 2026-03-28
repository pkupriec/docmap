# Configuration

Primary runtime config surfaces:
- `infra/docker-compose.yml`
- `.env.example`
- service defaults in `services/*`

## Core App Variables

- `DATABASE_URL`
- `EXTRACTOR_MODEL`
- `OLLAMA_HOST`
- `OLLAMA_TIMEOUT_SECONDS`
- `OLLAMA_THINK_LEVEL`
- `OLLAMA_NUM_PREDICT`
- `GEOCODER_URL` (code default if unset)
- `GEOCODER_MIN_INTERVAL_SECONDS`
- `GEOCODER_USER_AGENT`
- `LOG_LEVEL`
- `PYTHONUNBUFFERED`

## Startup Migration Variables

- `DB_RESET_ON_START`
- `DB_DROP_TABLES_ON_START`
- `DB_STARTUP_MAX_WAIT_SECONDS`
- `DB_STARTUP_RETRY_INTERVAL_SECONDS`

## Canonical Refresh Variables

- `CANONICAL_REFRESH_ON_GEOCODE`
- `CANONICAL_DICTIONARY_INPUT`
- `CANONICAL_DICTIONARY_SOURCE`
- `CANONICAL_REFRESH_REPORT_PATH`
- `CANONICAL_REFRESH_REPLACE_SOURCE`
- `CANONICAL_AUTOSEED_ON_EMPTY`
- `CANONICAL_BUILD_SEED_SOURCE_ON_REFRESH`
- `CANONICAL_SEED_SOURCE`

These are consumed by geocoder refresh logic in `services/geocoder/service.py`.

## BigQuery Export Variables

- `GCP_PROJECT_ID`
- `BIGQUERY_DATASET`
- `BIGQUERY_LOCATION`
- `GOOGLE_APPLICATION_CREDENTIALS`

## Scheduler Variables

Used by `services/pipeline/scheduler.py`:
- `SCHEDULER_CRON`
- `SCHEDULER_TIMEZONE`
- `SCHEDULER_MAX_RETRIES`

Scheduler is implemented but not auto-started in current app bootstrap.

## Presentation Runtime

- `DATABASE_URL` (required)
- `PRESENTATION_STATIC_DIR` (optional, defaults to built frontend path)