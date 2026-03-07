# Phase 1 - Database Layer

Goal: implement the operational and BI schema in PostgreSQL/PostGIS.

## Tasks

1. Enable required extensions:
   - `postgis`
   - `pgcrypto`
2. Create tables:
   - `scp_objects`
   - `documents`
   - `document_snapshots`
   - `extraction_runs`
   - `location_mentions`
   - `geo_locations`
   - `document_locations`
3. Create BI tables:
   - `bi_documents`
   - `bi_locations`
   - `bi_document_locations`
4. Create spatial index on `geo_locations.geom`.
5. Create operational indexes:
   - `documents(scp_object_id)`
   - `location_mentions(run_id)`
   - `document_locations(document_id)`
6. Add seed script to insert canonical IDs `SCP-001` to `SCP-7999` into `scp_objects`.

## Acceptance Criteria

- Running `database/schema.sql` on an empty DB succeeds without manual edits.
- All tables and indexes from this phase are present.
- Seeding inserts 7,999 unique SCP IDs and is idempotent.
