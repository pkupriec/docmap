# Changelog

All notable repository-level changes are documented here.

## [Unreleased]

### Extraction

- Added Ollama timeout + generation tuning controls:
  - `OLLAMA_TIMEOUT_SECONDS`
  - `OLLAMA_THINK_LEVEL`
  - `OLLAMA_NUM_PREDICT`
- Added extractor model selection via `EXTRACTOR_MODEL` (default `gpt-oss:20b`).
- Extended extractor Ollama success logging with timing/token metadata for performance diagnostics.
- Hardened extraction prompt (`services/extractor/prompts/location_extraction_prompt.md`) with:
  - anti-hallucination constraints
  - stricter normalization/canonicalization guidance
  - precision/confidence guidance
  - deduplication rules
  - few-shot examples
- Added DB index/migration hardening for extraction/geocoding query paths:
  - `uq_extraction_runs_snapshot_id` (unique by snapshot)
  - `idx_document_snapshots_document_created_desc`
  - `idx_document_snapshots_created_at_id`
  - `uq_document_locations_mention_id` (unique partial index)

### Geocoding

- Added Nominatim resilience improvements:
  - request throttling via `GEOCODER_MIN_INTERVAL_SECONDS`
  - 429-aware backoff (uses `Retry-After` when present)
  - fallback query variants for over-specific place names
- Geocoder now treats exhausted Nominatim retries as unresolved (`None`) instead of raising hard stage exceptions.
- Geocoder transaction granularity changed to atomic per mention (commit/rollback per item).
- Geocode stage progress semantics aligned:
  - `total_items` reflects pending backlog context
  - per-run processing still respects configured stage item limit
  - normalization sub-step now respects the same per-run limit

### Documentation

- Rewrote root architecture/project docs to match current code and schema:
  - `README.md`
  - `PROJECT.md`
  - `ARCHITECTURE.md`
  - `SERVICES.md`
  - `PIPELINE.md`
  - `DATA_MODEL.md`
- Added/updated operational documentation package:
  - `docs/CONFIGURATION.md`
  - `docs/DEVELOPMENT.md`
  - `docs/OPERATIONS.md`
  - `docs/VERIFICATION.md`
  - `docs/REPOSITORY_MAP.md`
  - `docs/CONTROL_API.md`

### Clarifications captured in docs

- Stage resume is implemented through control API and orchestrator logic.
- Snapshot storage uses `pdf_blob` (not `pdf_path`).
- Single active run policy and command queue behavior documented as implemented.
- BigQuery export requirements and failure mode documented.
- Scheduler presence documented as partial (module exists, not auto-started).

### Presentation Layer

- Implemented phase 11 presentation backend in `services/presentation/backend/*` with read-only endpoints:
  - `GET /api/map/locations`
  - `GET /api/map/location/{location_id}/documents`
  - `GET /api/map/document/{document_id}/locations`
  - `GET /api/map/overlays/density`
- Implemented hierarchy fallback in backend using BI hierarchy tables (`city -> region -> country`).
- Implemented dedicated presentation frontend app in `services/presentation/frontend/*` using React + Vite + TypeScript + MapLibre GL + deck.gl.
- Added separate presentation runtime/container:
  - `main_presentation.py`
  - `Dockerfile.presentation`
  - `presentation` service in `infra/docker-compose.yml`.
- Extended BI schema and analytics rebuild for presentation contract:
  - `bi_documents.preview_text`
  - `bi_locations.parent_location_id`
  - `bi_document_locations.evidence_quote`
  - `bi_location_hierarchy`.
