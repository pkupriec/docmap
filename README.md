# DocMap

DocMap is an operator-driven data pipeline for SCP Wiki documents:

`SCP Wiki -> Crawl -> Extraction (LLM) -> Geocoding -> Analytics -> BigQuery export`

## Current Status

- `implemented`: operational schema (`database/schema.sql`) and control-plane schema (`database/control_plane.sql`)
- `implemented`: control API + orchestrator (`services/control/*`)
- `implemented`: operator UI (`ui/`) with start/cancel/retry/retry-stage/resume-stage
- `implemented`: crawler/extractor/geocoder/analytics/export services
- `implemented`: presentation layer service (`services/presentation/*`) with read-only map API + dedicated UI
- `partial`: presentation mixed geometry exists, but current static boundary coverage is not sufficient for reliable real-geometry rendering
- `partial`: scheduler exists in code (`services/pipeline/scheduler.py`) but is not started by the main app
- `partial`: BigQuery export works when GCP env + credentials are configured
- `planned`: external publication/dashboard automation (Looker operationalization)
- `planned`: phase 13 real-geometry extension for `admin_region`, `country`, `continent`, and `ocean`, with `city` preserved as point geometry

## Quick Start (Docker)

1. Ensure Docker Desktop is running.
2. Start stack:
   `docker compose -f infra/docker-compose.yml up -d --build`
3. Open:
   - API: `http://localhost:8000`
   - Control UI: `http://localhost:5173`
   - Presentation UI/API: `http://localhost:8080`
   - pgAdmin: `http://localhost:5050`

## Extraction Runtime Tuning

Extractor/Ollama behavior is configurable via env vars (see `docs/CONFIGURATION.md`):

- `EXTRACTOR_MODEL` (default `gpt-oss:20b`)
- `OLLAMA_TIMEOUT_SECONDS` (default `300`)
- `OLLAMA_THINK_LEVEL` (default `low`)
- `OLLAMA_NUM_PREDICT` (optional output token cap)

## Key Entry Points

- App entrypoint: `main.py`
- Presentation entrypoint: `main_presentation.py`
- API app factory: `services/control/api.py:create_app`
- Presentation app factory: `services/presentation/backend/api.py:create_presentation_app`
- Orchestrator: `services/control/orchestrator.py`
- Compose: `infra/docker-compose.yml`
- DB schemas:
  - `database/schema.sql`
  - `database/control_plane.sql`

## Documentation Index

- Project scope/status: [PROJECT.md](PROJECT.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Service boundaries: [SERVICES.md](SERVICES.md)
- Pipeline behavior: [PIPELINE.md](PIPELINE.md)
- Data model: [DATA_MODEL.md](DATA_MODEL.md)
- Configuration: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- Development workflow: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- Operations runbook: [docs/OPERATIONS.md](docs/OPERATIONS.md)
- Verification guide: [docs/VERIFICATION.md](docs/VERIFICATION.md)
- Repository map: [docs/REPOSITORY_MAP.md](docs/REPOSITORY_MAP.md)
- Control API: [docs/CONTROL_API.md](docs/CONTROL_API.md)
- Change history: [CHANGELOG.md](CHANGELOG.md)
- Map geometry handoff: [AGENT/MAP_GEOMETRY_HANDOFF.md](AGENT/MAP_GEOMETRY_HANDOFF.md)
