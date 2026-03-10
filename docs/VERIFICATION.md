# Verification

This guide defines concrete checks for documentation/code consistency.

## Baseline Verification Commands

1. Compose validity:
`docker compose -f infra/docker-compose.yml config`

2. Python compile check (selected modules):
`docker compose -f infra/docker-compose.yml exec -T app python -m py_compile services/control/api.py services/control/orchestrator.py`

3. API smoke:
- `GET /api/runs`
- `GET /api/runs/{id}` for an existing run

4. UI build:
`docker compose -f infra/docker-compose.yml exec -T control-ui sh -lc "cd /app/ui && npm run -s build"`

## Cross-Checks Performed For This Documentation Refresh

### Entrypoints

- `main.py` loads `create_app()` from control API (`implemented`).
- Scheduler module exists but is not app-started (`partial`).

### Database

- `database/schema.sql` uses `document_snapshots.pdf_blob` (not `pdf_path`).
- `database/control_plane.sql` defines control-plane tables and enums (`implemented`).

### Runtime config

- `infra/docker-compose.yml` includes app/postgres/control-ui/pgadmin (`implemented`).
- Extractor/Ollama tuning env vars are present (`EXTRACTOR_MODEL`, `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_THINK_LEVEL`, `OLLAMA_NUM_PREDICT`).
- BigQuery env values are present but empty by default (`partial until operator config`).

### Service/module layout

- `services/*` packages match current architecture boundaries (`implemented`).

## Mismatches Found and Resolved (Docs)

1. Old docs referenced `pdf_path`; code/schema use `pdf_blob`.
2. Old docs claimed pause/resume as non-goal in phase text; current implementation includes stage resume endpoint and logic.
3. Old docs did not document `/api/runs/{run_id}/stages/{stage_name}/resume`.
4. Old docs did not reflect current control-plane command/run behavior and UI actions.
5. Old docs had stale/garbled encoding artifacts; replaced with clean UTF-8 text.

## Remaining Gaps (Intentionally Marked)

- Scheduler auto-start integration (`partial`)
- AuthN/AuthZ for control API/UI (`planned`)
- Production deployment/backup playbooks (`planned`)
