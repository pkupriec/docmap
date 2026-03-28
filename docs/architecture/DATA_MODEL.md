# Data Model

Schema authority:
- `database/schema.sql`
- `database/control_plane.sql`

## Operational Tables

- `scp_objects`
- `documents`
- `document_snapshots` (`raw_html`, `clean_text`, `pdf_blob`)
- `extraction_runs`
- `location_mentions`
- `geo_locations`
- `geo_canonical_places`
- `geo_canonical_aliases`
- `geo_canonical_concordances`
- `document_locations`

`geo_locations` includes canonical resolution metadata and OSM identity fields.

## BI Tables

- `bi_documents`
- `bi_locations`
- `bi_document_locations`
- `bi_location_hierarchy`
- `bi_admin_boundaries`

`bi_document_locations` fields are:
- `document_id`
- `location_id`
- `mention_count`
- `evidence_quote`
- `updated_at`

It does not store `confidence` or `precision`.

## Control Plane Tables

- `pipeline_runs`
- `pipeline_stage_runs`
- `pipeline_progress`
- `pipeline_logs`
- `pipeline_commands`

## Invariants

- snapshots are historical records
- derived analytics projections are rebuildable
- control-plane state is operational metadata, separate from domain facts