# Verification

## Baseline Checks

1. `docker compose -f infra/docker-compose.yml config`
2. `docker compose -f infra/docker-compose.yml exec -T app pytest -q`
3. `GET http://localhost:8000/api/runs`
4. `GET http://localhost:8080/healthz`
5. `GET http://localhost:8080/api/map/locations`

## Startup Reproducibility Check

1. Start stack on clean system: `docker compose -f infra/docker-compose.yml up -d --build`
2. Confirm app startup migrations ran without manual SQL.
3. On existing DB volumes, confirm runtime patches include Phase 19 geocoder columns:
   - `geo_locations.osm_admin_level`
   - `geo_locations.boundary_intent`
   - `geo_locations.geocode_candidates`

## Contract Consistency Checks

- Confirm control API includes stage resume endpoint.
- Confirm presentation API includes boundaries, document card, document PDF, and search endpoints.
- Confirm location-documents response includes pagination and scope metadata.
- Confirm schema/docs alignment for canonical geo fields and `bi_document_locations` columns.
- Confirm boundaries endpoint supports additive params:
  - `rank_filter=default|all`
  - `geometry_detail=low|full`

## Presentation Rendering Performance Checks

1. Start presentation stack and open browser console.
2. Load presentation root once and record:
   - `presentation.performance.first_meaningful_render_ms`
   - `presentation.performance.boundaries_ready_ms`
3. Measure boundaries endpoint payload and latency for variants:
   - `lite=1&rank_filter=default` (default full detail)
   - `lite=1&rank_filter=default&geometry_detail=low`
   - `lite=1&rank_filter=all&geometry_detail=low`
   - `lite=1&rank_filter=all&geometry_detail=full`
4. For each variant, record:
   - decoded JSON bytes
   - encoded payload bytes
   - endpoint latency cold/warm

## Canonical Refresh Smoke

1. Run `canonical-refresh` profile.
2. Verify report JSON exists at `CANONICAL_REFRESH_REPORT_PATH`.
3. Verify report includes counts for places/aliases/concordances.

## Geocode Refresh Behavior Check

1. Start `geocode_only` run with `target_scope=all`.
2. Verify default options behavior in run payload/logs:
   - canonical refresh enabled
   - missing-identity refresh enabled
3. Start a second run with `options.full_refresh_geo_information=true`.
4. Verify geocoder logs show cached rows being re-geocoded (not only linked).

## Known Gaps

- scheduler auto-start in app runtime
- authn/authz hardening
- production backup/disaster recovery playbooks
