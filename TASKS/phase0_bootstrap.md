# Phase 0 - Project Bootstrap

Goal: prepare a runnable baseline for all later phases.

Scope limits:
- No crawling, extraction, geocoding, analytics, or BigQuery logic.
- Only project scaffolding, config, runtime boot, and test boot.

## Tasks

1. Create `pyproject.toml` for Python 3.11+ with runtime and test dependencies.
2. Ensure directories exist:
   - `services/crawler`
   - `services/extractor`
   - `services/geocoder`
   - `services/pipeline`
   - `services/analytics`
   - `services/common`
   - `database`
   - `infra`
   - `tests`
3. Create empty `__init__.py` in each `services/*` package.
4. Create `.env.example` with:
   - `DATABASE_URL=postgresql://docmap:docmap@postgres:5432/docmap`
   - `OLLAMA_HOST=http://host.docker.internal:11434`
   - `OLLAMA_TIMEOUT_SECONDS=300`
   - `OLLAMA_THINK_LEVEL=low`
   - `OLLAMA_NUM_PREDICT=`
   - `EXTRACTOR_MODEL=gpt-oss:20b`
   - `GEOCODER_URL=https://nominatim.openstreetmap.org`
5. Implement `services/common/logging.py` with a shared `configure_logging()` helper.
6. Implement `services/common/db.py` using `DATABASE_URL`.
7. Create `main.py` entrypoint that boots logging and prints a startup message.
8. Add `tests/test_bootstrap.py` and configure `pytest`.
9. Create a root `Dockerfile` used by `infra/docker-compose.yml`.
10. Verify compose boot:
    - `postgres` starts
    - schema auto-loads
    - app container starts cleanly

## Acceptance Criteria

- `docker compose -f infra/docker-compose.yml up --build` succeeds.
- `pytest` runs and passes at least the bootstrap test.
- App container imports project modules without import errors.
- No Phase 1+ functionality exists yet.
