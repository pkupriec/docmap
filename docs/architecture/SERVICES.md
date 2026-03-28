# Service Boundaries

## Table Ownership

- crawler: `scp_objects`, `documents`, `document_snapshots`
- extractor: `extraction_runs`, `location_mentions`
- geocoder: `geo_locations`, `document_locations`, canonical dictionary refresh inputs
- analytics: `bi_documents`, `bi_locations`, `bi_document_locations`, `bi_location_hierarchy`, `bi_admin_boundaries`
- control: `pipeline_runs`, `pipeline_stage_runs`, `pipeline_progress`, `pipeline_logs`, `pipeline_commands`
- presentation: read-only queries over BI/runtime tables

## Service Responsibilities

Crawler (`services/crawler/*`):
- deterministic SCP URL generation
- fetch/parse/snapshot persistence
- PDF render/backfill

Extractor (`services/extractor/*`):
- prompt build and LLM call
- mention validation/persistence
- per-snapshot processing semantics

Geocoder (`services/geocoder/*`):
- mention normalization
- Nominatim resolution and cache update
- canonical identity mapping and ambiguity resolution
- document-location linking

Analytics (`services/analytics/*`):
- deterministic rebuild of BI projections
- boundaries materialization into `bi_admin_boundaries`
- optional BigQuery export

Control (`services/control/*`):
- command enqueue API
- orchestrator command/run lifecycle handling
- observability tables and event stream

Presentation (`services/presentation/*`):
- map/document/search read API
- static frontend delivery
- no write-side responsibilities

## Boundary Rules

- Services may read cross-domain tables only when required by pipeline flow.
- Write ownership must stay strict by service.
- Presentation must not call pipeline stage code directly.