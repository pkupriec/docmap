# Operations Runbook

## Local Endpoints

- Control API: `http://localhost:8000`
- Control UI: `http://localhost:5173`
- Presentation runtime: `http://localhost:8080`
- pgAdmin: `http://localhost:5050`

## Compose Lifecycle

Start:
`docker compose -f infra/docker-compose.yml up -d --build`

Stop:
`docker compose -f infra/docker-compose.yml down`

## Health and Logs

- `docker compose -f infra/docker-compose.yml ps`
- `docker compose -f infra/docker-compose.yml logs --tail=200 app`
- `docker compose -f infra/docker-compose.yml logs --tail=200 presentation`

Performance-focused presentation logs:
- `presentation.api_request` for endpoint timing/payload size on:
  - `/api/map/locations`
  - `/api/map/boundaries`
  - `/api/map/location/{location_id}/documents`
  - `/api/map/document/{document_id}/locations`
  - `/api/search`
- repository timing logs:
  - `presentation.locations_repo_fetch`
  - `presentation.boundaries_repo_fetch`
  - `presentation.resolve_location_for_documents`
  - `presentation.location_documents_repo_fetch`
  - `presentation.document_locations_repo_fetch`
  - `presentation.search_repo_fetch`

## Control API Operations

- `POST /api/runs`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/runs/{run_id}/retry`
- `POST /api/runs/{run_id}/stages/{stage_name}/retry`
- `POST /api/runs/{run_id}/stages/{stage_name}/resume`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/logs`
- `GET /api/runs/{run_id}/events`

## Geocode Reprocessing Modes

Standard full geocode refresh (default behavior):
- canonical dictionary refresh is enabled by default
- refresh of missing geo identity/candidate fields is enabled by default

From-scratch geo refresh:
- set `options.full_refresh_geo_information=true` on `POST /api/runs`
- this forces re-geocode of cached rows instead of linking existing cache

UI behavior:
- Control UI exposes one geocode/full toggle:
  `Full refresh of geoinformation (re-geocode all cached geo rows from scratch)`
- canonical refresh and missing-identity refresh are default-on and not shown as separate toggles

## Presentation API Operations

- `GET /api/map/locations`
- `GET /api/map/boundaries`
- `GET /api/map/location/{location_id}/documents`
- `GET /api/map/document/{document_id}`
- `GET /api/map/document/{document_id}/pdf`
- `GET /api/map/document/{document_id}/locations`
- `GET /api/map/overlays/density`
- `GET /api/search`
- `GET /healthz`

## Presentation Hot-Path Index Audit

Present and in active runtime use:
- `idx_bi_admin_boundaries_rank`
- `idx_bi_admin_boundaries_lat_bounds`
- `idx_bi_admin_boundaries_lon_bounds`
- `idx_bi_document_locations_location`
- `idx_bi_document_locations_location_document`
- `idx_bi_location_hierarchy_ancestor_depth`
- `idx_bi_location_hierarchy_descendant_depth`
- primary keys on `bi_documents`, `bi_locations`, and `bi_document_locations`

Known missing or weak for current hot paths:
- no canonical search-support indexes for `LOWER(...) LIKE` on:
  - `bi_documents.canonical_number`
  - `bi_locations.normalized_location`
  - `bi_locations.city`
  - `bi_locations.region`
  - `bi_locations.country`
- no canonical presentation-order index for the startup `bi_locations` read ordered by `document_count DESC, normalized_location ASC, location_id ASC`
- no canonical document-first helper index for `/api/map/document/{document_id}/locations` ordering by `mention_count DESC`

These are audit findings only for Phase A. Search and lookup index hardening stays in later remediation phases.

## Admin Boundaries Rebuild

Use the dedicated analytics script when boundary matching or geometry selection changes and you need a reproducible refresh of `bi_admin_boundaries`.

Rebuild source dataset + DB boundaries:
`docker compose -f infra/docker-compose.yml exec -T app python -m services.analytics.scripts.rebuild_admin_boundaries`

If only boundary matching/selection logic changed and the source dataset itself does not need refresh, reuse the existing source file:
`docker compose -f infra/docker-compose.yml exec -T app sh -lc "DOCMAP_ADMIN_BOUNDARIES_REFRESH_SOURCE=0 python -m services.analytics.scripts.rebuild_admin_boundaries"`

After rebuild, restart presentation to clear its in-memory boundaries cache:
`docker compose -f infra/docker-compose.yml restart presentation`

Expected outputs:
- `services/analytics/assets/admin_boundaries_source.geojson` refreshed from source inputs
- `services/analytics/assets/admin_boundaries.geojson` rewritten from current DB targets
- `services/analytics/assets/admin_boundaries.coverage.json` rewritten
- `services/analytics/assets/presentation_geometry/current.json` rewritten
- `services/analytics/assets/presentation_geometry/{version}/manifest.json` written
- `services/analytics/assets/presentation_geometry/{version}/{mode}/z/x/y.mvt` written for:
  - `full_precise`
  - `balanced_precise`
  - `simplified`
  - `primitive`
- `bi_admin_boundaries` refreshed without manual SQL or ad hoc DB patches

If an existing DB was built before a generic-ocean merge fix landed and you need a deterministic backfill without a full boundaries rebuild, run:
`docker compose -f infra/docker-compose.yml exec -T app python -m services.analytics.scripts.backfill_generic_ocean_boundaries`

Then restart presentation:
`docker compose -f infra/docker-compose.yml restart presentation`

## Canonical Dictionary Refresh

One-shot via offline profile:
`docker compose -f infra/docker-compose.yml --profile offline-tools run --rm canonical-refresh`

Manual from app image:
`docker compose -f infra/docker-compose.yml run --rm app sh -lc "python -m services.geocoder.scripts.refresh_canonical_dictionary --input \"$CANONICAL_DICTIONARY_INPUT\" --source \"$CANONICAL_DICTIONARY_SOURCE\" --report \"$CANONICAL_REFRESH_REPORT_PATH\" --replace-source"`

Expected outputs:
- canonical tables updated
- refresh report JSON at configured report path

## Common Failure Cases

- BigQuery export fails: missing project/credentials config.
- UI proxy errors: app restarting or unavailable.
- Long geocode runs: review rate limits and geocoder env tuning.
- Stuck commands: inspect `/api/commands/{command_id}` and active run state.
