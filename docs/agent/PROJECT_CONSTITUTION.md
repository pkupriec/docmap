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

## Persistent Implementation Rules

The following implementation rules are treated as carry-forward defaults unless a newer phase/user directive overrides them:

- clean-start reproducibility: `docker compose up` on a clean system must be sufficient to run current behavior without manual DB SQL
- existing-db reproducibility: startup/runtime migrations must patch schema changes needed by new code paths
- geometry loading policy: if a location is geocoded, geometry lookup should be attempted regardless of specific OSM tag/class naming
- hierarchy policy for polygon geographies: support multi-country and multi-admin links via deterministic spatial intersection when geometry exists
- UI control policy for geocode refresh:
  - canonical dictionary refresh is default-on
  - missing-identity refresh is default-on
  - explicit user control is provided only for from-scratch full geo refresh
