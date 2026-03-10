# Development

## Local Prerequisites

- Docker Desktop
- Python 3.11+ (optional for host tooling)
- Node/npm are not required on host when using compose

## Start Development Stack

`docker compose -f infra/docker-compose.yml up -d --build`

Services:
- `postgres` on `5432`
- `app` on `8000`
- `control-ui` on `5173`
- `presentation` on `8080`
- `pgadmin` on `5050`

## Recommended Dev Loop

1. Edit Python code under `services/`.
2. App auto-reloads (`uvicorn --reload`).
3. Use UI at `http://localhost:5173` for control-plane scenarios.
4. Inspect logs:
   `docker compose -f infra/docker-compose.yml logs -f app`
5. Presentation UI is available at `http://localhost:8080`.

## Extractor Tuning During Development

Useful env vars in `infra/docker-compose.yml` / `.env`:
- `EXTRACTOR_MODEL`
- `OLLAMA_TIMEOUT_SECONDS`
- `OLLAMA_THINK_LEVEL`
- `OLLAMA_NUM_PREDICT`

Prompt file used by extraction:
- `services/extractor/prompts/location_extraction_prompt.md`

## Tests

Run tests inside app container:

`docker compose -f infra/docker-compose.yml exec -T app pytest -q`

## Build Checks

- Python syntax:
  `docker compose -f infra/docker-compose.yml exec -T app python -m py_compile <files...>`
- UI build:
  `docker compose -f infra/docker-compose.yml exec -T control-ui sh -lc "cd /app/ui && npm run -s build"`
- Presentation image build:
  `docker compose -f infra/docker-compose.yml build presentation`

## Coding Boundaries

- `implemented`: service ownership is enforced by repository conventions
- `partial`: static architecture enforcement/linting is not automated

## Migration Behavior in Dev

By default, startup does not reset DB (`DB_RESET_ON_START=0`).

To re-apply schema from SQL files in a clean-slate mode, set:
- `DB_RESET_ON_START=1`
- optionally `DB_DROP_TABLES_ON_START=1`

Use with care: this may drop local runtime metadata.
