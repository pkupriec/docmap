# Project Constitution

DocMap maps SCP documents to real-world locations mentioned in document text.

Non-negotiable invariants:
- pipeline order is `crawl -> extract -> geocode -> analytics -> export`
- snapshots are historical records; changed content creates a new snapshot
- service/table ownership boundaries stay explicit
- presentation is a separate read-only runtime over BI/runtime projections
- control API enqueues commands; orchestrator applies run/stage mutations
- architecture changes must be explicit and documented

Write boundaries:
- crawler: `scp_objects`, `documents`, `document_snapshots`
- extractor: `extraction_runs`, `location_mentions`
- geocoder: `geo_locations`, `document_locations`, canonical dictionary refresh side effects
- analytics: `bi_*`
- control: `pipeline_*`
- presentation: no writes

Implementation authority:
- schema truth: `database/schema.sql`, `database/control_plane.sql`
- runtime topology truth: `infra/docker-compose.yml`
- behavior truth: `services/*`

If prose conflicts with implementation, fix docs or flag the inconsistency.