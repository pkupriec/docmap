# Data Model Summary

Operational facts:

- crawled content lives in `documents` and `document_snapshots`
- extracted mentions live in `location_mentions`
- resolved geocoding lives in `geo_locations` and `document_locations`
- canonical geo identity dictionary lives in:
  - `geo_canonical_places`
  - `geo_canonical_aliases`
  - `geo_canonical_concordances`
- `geo_locations` can carry canonical linkage metadata (`canonical_id`, method, confidence)

Derived analytics:

- presentation and BI consumers read `bi_documents`, `bi_locations`, `bi_document_locations`, and `bi_location_hierarchy`

Control plane:

- run, stage, progress, log, and command state live in `pipeline_*` tables

Key invariants:

- snapshots are historical records
- derived data does not belong in source tables
- presentation consumes BI projections only

Read [DATA_MODEL.md](D:/Sources/docmap/DATA_MODEL.md) plus `database/schema.sql` for full schema authority.
