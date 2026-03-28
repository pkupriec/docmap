# Project Constitution

DocMap maps SCP documents to real-world locations mentioned in document text. The core unit is the document, not the SCP object.

Non-negotiable invariants:

- pipeline order is `crawl -> extract -> geocode -> analytics -> export`
- `document_snapshots` are immutable historical records; changed content creates a new snapshot
- extraction writes mentions, geocoding writes resolved locations and links, analytics writes `bi_*`, presentation writes nothing
- services stay logically separate even if they share a repo or container
- BI and presentation consume derived data; they do not repurpose operational tables as their source of truth
- presentation is a read-only service over BI/runtime projections and document PDFs
- hierarchy fallback for document discovery remains `city -> region -> country`
- `continent` and `ocean` are rendering classes, not new fallback targets
- architecture changes must be explicit; do not silently redesign around a local task

Write boundaries:

- crawler: `scp_objects`, `documents`, `document_snapshots`
- extractor: `extraction_runs`, `location_mentions`
- geocoder: `geo_locations`, `document_locations`
- analytics: `bi_*`
- control plane: `pipeline_*`
- presentation: no table writes

Implementation authority:

- schema truth lives in `database/schema.sql` and `database/control_plane.sql`
- runtime topology truth lives in `infra/docker-compose.yml`
- if prose conflicts with code/schema/runtime, treat that as a documentation defect and fix the docs when the task allows documentation edits
