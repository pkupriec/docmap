# Checkpoint 5 Summary (Pipeline/Domain Docs)

Date: 2026-03-29

## Scope Reviewed

Code/Runtime:
- `services/{crawler,extractor,geocoder,analytics,pipeline,common}/*`
- `services/control/orchestrator.py`
- `database/schema.sql`
- `database/control_plane.sql`
- `infra/docker-compose.yml`
- `.env.example`

Docs:
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/DATA_MODEL.md`
- `docs/architecture/SERVICES.md`
- `docs/architecture/PIPELINE.md`
- `docs/architecture/PIPELINE.summary.md`
- `docs/operations/{CONFIGURATION.md,OPERATIONS.md,VERIFICATION.md,DEVELOPMENT.md}`

## Alignment Outcome

Checkpoint 5 performed focused architecture/pipeline doc alignment with no service-code changes.

Updated docs:
- `docs/architecture/PIPELINE.md`
- `docs/architecture/PIPELINE.summary.md`

## Behavior Facts Locked

- `process_unprocessed_only` mode ignores `refresh_geo_identity` and `full_refresh_geo_information` flags during geocode execution.
- geocode stage resume with saved progress (`current_index > 0`) skips canonical dictionary refresh on resumed execution.
- scheduler module remains implemented but not auto-started from `main.py` (already documented and reconfirmed).
- configuration and operations docs for core env surfaces and compose services were reviewed and found consistent with current runtime.

## Ready For

Checkpoint 6: verification run and final consistency sweep across all modified docs.
