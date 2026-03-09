# Repository Map

Top-level structure and current role.

## Root

- `main.py` - app entrypoint
- `pyproject.toml` - Python package/dependency config
- `Dockerfile` - app image build
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
- `geocoder/`
  - normalization, geocode client/repository/service
- `analytics/`
  - BI table rebuild + BigQuery export
- `pipeline/`
  - direct pipeline runner + scheduler module
- `control/`
  - FastAPI routes, orchestrator, repository, schemas, constants

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
