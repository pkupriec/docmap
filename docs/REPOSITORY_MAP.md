# Repository Map

Top-level structure and current role.

## Root

- `main.py` - app entrypoint
- `main_presentation.py` - presentation service entrypoint
- `pyproject.toml` - Python package/dependency config
- `Dockerfile` - app image build
- `Dockerfile.presentation` - presentation image build
- `README.md` - first-entry documentation
- `PROJECT.md`, `ARCHITECTURE.md`, `SERVICES.md`, `PIPELINE.md`, `DATA_MODEL.md` - source-of-truth docs
- `CHANGELOG.md` - repo change log

## `services/`

- `common/`
  - `db.py` connection helper
  - `logging.py` log configuration
  - `migrations.py` startup schema behavior
- `crawler/`
  - URL generation, download, parsing, snapshot persistence
- `extractor/`
  - prompting, LLM call, validation, persistence
  - key files:
    - `prompt_builder.py`
    - `ollama_client.py`
    - `prompts/location_extraction_prompt.md`
- `geocoder/`
  - normalization, geocode client/repository/service
- `analytics/`
  - BI table rebuild + BigQuery export
- `pipeline/`
  - direct pipeline runner + scheduler module
- `control/`
  - FastAPI routes, orchestrator, repository, schemas, constants
- `presentation/`
  - `backend/` read-only presentation API/query layer
  - `frontend/` dedicated React/Vite/TypeScript map UI

## `database/`

- `schema.sql` - operational + BI schema
- `control_plane.sql` - control-plane schema
- `seed_scp_objects.sql` - canonical SCP seed data

## `infra/`

- `docker-compose.yml` - local runtime topology
- `pgadmin/servers.json` - pgAdmin preconfigured server

## `ui/`

- React/Vite operator UI
- key file: `ui/src/App.jsx`

## `services/presentation/frontend/`

- dedicated presentation UI app (React + Vite + TypeScript + MapLibre GL + deck.gl)

## `docs/`

- `CONTROL_UI.md` - UI spec (legacy/spec-oriented)
- `CONTROL_API.openapi.yaml` - API schema artifact
- `CONFIGURATION.md`, `DEVELOPMENT.md`, `OPERATIONS.md`, `VERIFICATION.md`, `REPOSITORY_MAP.md`, `CONTROL_API.md` - current operator/developer docs

## `TASKS/`

Phase documents used as implementation intent/history.

## `tests/`

Automated test suite for selected behavior.

## Non-source runtime dirs

- `secrets/` - local credentials mounts
- `snapshots/` - generated artifacts
