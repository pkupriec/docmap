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

### `geo_locations`
- resolved normalized locations + PostGIS geography point
- unique `normalized_location`

### `document_locations`
- link table between document and geocoded location

## BI Tables (`implemented`)

- `bi_documents`
- `bi_locations`
- `bi_document_locations`

These are rebuildable denormalized analytics tables.

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
