# Data Model

This document reflects the current SQL schema in:
- `database/schema.sql`
- `database/control_plane.sql`

## Operational Domain Tables (`implemented`)

### `scp_objects`
- canonical SCP IDs
- key: `id` UUID, unique `canonical_number`

### `documents`
- canonical document URLs and metadata
- key: `id` UUID, unique `url`
- includes `last_checked_at`

### `document_snapshots`
- content snapshots
- columns: `raw_html`, `clean_text`, `pdf_blob` (`BYTEA`)

### `extraction_runs`
- extraction execution metadata per snapshot

### `location_mentions`
- extracted mentions from LLM output
- includes `mention_text`, `normalized_location`, `precision`, `relation_type`, `confidence`, `evidence_quote`

### `geo_locations`
- resolved normalized locations + PostGIS geography point
- unique `normalized_location`

### `document_locations`
- link table between document and geocoded location

### Current BI Tables (`implemented`)
- `bi_documents`
- `bi_locations`
- `bi_document_locations`
- `bi_location_hierarchy`

These are rebuildable denormalized analytics tables.

Presentation extensions now implemented in BI schema:

- document preview fields in `bi_documents`
- hierarchy support in `bi_locations.parent_location_id` and `bi_location_hierarchy`
- evidence quote support in `bi_document_locations`

The presentation layer must consume BI projections only.
Operational tables remain the source of truth for extraction/geocoding stages.

## Control Plane Tables (`implemented`)

### `pipeline_runs`
- run lifecycle, status, target scope, parameters JSON

### `pipeline_stage_runs`
- per-stage status and counters for a run

### `pipeline_progress`
- latest progress cursor per run+stage

### `pipeline_logs`
- operator-facing persisted logs

### `pipeline_commands`
- command queue consumed by orchestrator

## Enumerations/Constraints (`implemented`)

Control-plane SQL defines enums/checks for:
- run statuses
- stage statuses
- command statuses
- command types
- pipeline type enum

## Notes

- `implemented`: log retention helper function keeps logs for most recent 10 runs
- `partial`: no explicit schema migration history table; startup migration logic is environment-driven and idempotent where possible
- `planned`: presentation-oriented BI projections must remain rebuildable from operational tables
- `planned`: BI schema extensions for presentation must preserve portability toward BigQuery-style analytical storage
