# Configuration

This document describes runtime configuration for the current implementation.

## Source of Truth

- Runtime container env: `infra/docker-compose.yml` (`app.environment`)
- Code-level defaults: service modules (`services/*`)

## Required Variables (App Runtime)

### Core

- `DATABASE_URL` (`implemented`, required)
  - used by `services/common/db.py`
- `OLLAMA_HOST` (`implemented`, optional with default)
  - default in code: `http://localhost:11434`
- `OLLAMA_TIMEOUT_SECONDS` (`implemented`, optional with default)
  - default in code: `300`
  - invalid or non-positive values fall back to default
- `LOG_LEVEL` (`implemented`)
- `PYTHONUNBUFFERED` (`implemented`)

### Startup migration controls

- `DB_RESET_ON_START` (`implemented`)
- `DB_DROP_TABLES_ON_START` (`implemented`)
- `DB_STARTUP_MAX_WAIT_SECONDS` (`implemented`, optional)
- `DB_STARTUP_RETRY_INTERVAL_SECONDS` (`implemented`, optional)

### Stage processing limit

- `DOCMAP_STAGE_ITEM_LIMIT` (`implemented`)
  - unset in code -> `20`
  - empty / `all` / `0` -> unlimited
  - positive integer -> explicit limit
- current compose value: `8000` (`implemented` local default)

### BigQuery export

- `GCP_PROJECT_ID` (`required` for export)
- `BIGQUERY_DATASET` (default in code: `docmap_mvp`)
- `BIGQUERY_LOCATION` (default in code: `US`)
- `GOOGLE_APPLICATION_CREDENTIALS` (path inside container)

## Compose Mounts

`app` mounts:
- project root -> `/app`
- `../secrets/gcp-sa.json` -> `/secrets/gcp-sa.json:ro`

## Scheduler Variables

Used by `services/pipeline/scheduler.py`:
- `SCHEDULER_CRON` (default `0 3 * * 1`)
- `SCHEDULER_TIMEZONE` (default `UTC`)
- `SCHEDULER_MAX_RETRIES` (default `2`)

Status:
- `partial`: scheduler module is configurable but not auto-started by `main.py`.

## UI Configuration

- Vite runtime base path:
  - `VITE_API_BASE` (default `/api`)

## Secret Handling

- `implemented`: credentials expected via mounted file path
- `partial`: no secret vault integration
- `planned`: production secret management conventions
