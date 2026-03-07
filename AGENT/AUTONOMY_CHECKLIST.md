# Autonomous Development Checklist

Purpose: define minimum clarity required for low-supervision implementation.

## Global Readiness Gates

- [ ] Phase files are internally consistent with `database/schema.sql`.
- [ ] `PIPELINE.md` and `SERVICES.md` have parseable Markdown and explicit contracts.
- [ ] Build/runtime bootstrap is runnable (`Dockerfile`, compose, pytest).
- [ ] Incremental processing rule is deterministic.
- [ ] BigQuery export contract is explicit (dataset, table mapping, write mode).
- [ ] Scheduler trigger, retry, and overlap policy are explicit.

## Canonical Decisions

1. Change detection
   - Use `sha256(clean_text)` and compare with latest stored snapshot text hash.
   - New snapshot only for first-seen, changed hash, or explicit resnapshot.
2. BigQuery targets
   - Dataset: `${GCP_PROJECT_ID}.${BIGQUERY_DATASET}`.
   - Tables: `bi_documents`, `bi_locations`, `bi_document_locations`.
3. Scheduler default
   - Weekly Monday 03:00 UTC (`0 3 * * 1`).
   - Skip overlapping run if prior run is still active.
4. Database phase contract
   - Extensions: `postgis`, `pgcrypto`.
   - Index reference: `documents(scp_object_id)`.

## Per-Phase Completion Gates

- Phase 0: `docker compose up --build` and `pytest` both succeed.
- Phase 1: schema + indexes + seed script are idempotent.
- Phase 2: unchanged pages do not create duplicate snapshots.
- Phase 3: invalid JSON retries and failures are isolated per snapshot.
- Phase 4: normalization updates only `normalized_location`.
- Phase 5: geocoder cache prevents duplicate external lookups.
- Phase 6: BI rebuild is rerunnable and read-only to operational tables.
- Phase 7: full and incremental BigQuery export modes both work.
- Phase 8: scheduled run triggers, logs run ID, and enforces single-flight.
