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
- Confirm canonical schema/docs include `bi_admin_boundaries` envelope support:
  - `min_lon`
  - `min_lat`
  - `max_lon`
  - `max_lat`
  - `idx_bi_admin_boundaries_rank`
  - `idx_bi_admin_boundaries_lat_bounds`
  - `idx_bi_admin_boundaries_lon_bounds`
- Confirm boundaries endpoint supports additive params:
  - `rank_filter=default|all`
  - `ranks={csv}`
  - `selected_location_id={uuid}`
  - `highlighted_location_ids={uuid,...}`
- Confirm baked geometry endpoints are available:
  - `GET /api/map/baked/manifest?mode=balanced_precise`
  - `GET /api/map/baked/tile-index?mode=balanced_precise`
  - `GET /api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt`
- Confirm runtime default precision config is honored:
  - set `DOCMAP_PRESENTATION_DEFAULT_PRECISION_MODE` (for example `full_precise`) in presentation runtime env
  - `GET /api/map/baked/manifest` returns `default_mode` and `mode` matching configured value

## Admin Boundaries Rebuild Check

1. Run:
   `docker compose -f infra/docker-compose.yml exec -T app python -m services.analytics.scripts.rebuild_admin_boundaries`
2. Restart presentation:
   `docker compose -f infra/docker-compose.yml restart presentation`
3. Verify:
   - `GET http://localhost:8080/healthz`
   - `GET http://localhost:8080/api/map/baked/manifest?mode=balanced_precise`
4. Confirm the rebuild completed without manual DB updates and baked manifest responds.
5. Confirm baked artifact outputs were regenerated:
   - `services/analytics/assets/presentation_geometry/current.json`
   - `services/analytics/assets/presentation_geometry/{version}/manifest.json`
   - all four mode directories exist in that version:
     - `full_precise`
     - `balanced_precise`
     - `simplified`
     - `primitive`

If validating a backfill-only rollout for pre-existing ocean rows:
1. Run:
   `docker compose -f infra/docker-compose.yml exec -T app python -m services.analytics.scripts.backfill_generic_ocean_boundaries`
2. Restart presentation.
3. Confirm the affected ocean boundary is present through `GET /api/map/boundaries`.

## Presentation Rendering Performance Checks

1. Start presentation stack and open browser console.
2. Load presentation root once and record:
   - `presentation.performance.first_meaningful_render_ms`
   - `presentation.performance.boundaries_ready_ms`
3. Confirm startup emits `GET /api/map/baked/manifest` and baked tile requests.
4. Confirm normal pan/zoom emits baked tile requests but no broad `/api/map/boundaries` requests.
5. Measure explicit overlay `/api/map/boundaries` payload/latency for representative selection/highlight requests, for example:
   - `lite=1&rank_filter=all&selected_location_id={uuid}`
   - `lite=1&rank_filter=all&highlighted_location_ids={uuid1},{uuid2}`
6. For each explicit variant, record:
   - decoded JSON bytes
   - encoded payload bytes
   - endpoint latency cold/warm
   - feature count
7. During pan/zoom + focus interactions, confirm:
  - normal-view geometry remains baked-tile driven
  - selection/highlight changes trigger explicit polygon requests only
  - stale explicit responses do not overwrite newer explicit-focus state
8. Switch session precision mode in the left panel and confirm:
   - a new baked manifest request is emitted with `mode=<selected_mode>`
   - a new baked tile-index request is emitted with `mode=<selected_mode>`
   - baked status transitions through loading and returns to ready
   - selection/highlight state remains intact
9. During prolonged idle map viewing, confirm background preload progress advances and pauses/resumes with viewport movement.

## Phase F Performance Validation (Baked Canonical Path)

Use the dedicated Phase F harness for repeatable baseline-vs-current comparisons:

1. Preflight baked readiness:
   - `GET http://localhost:8080/api/map/baked/manifest` must return `200`.
   - If it returns `404`, generate analytics-owned baked artifacts first.
2. Preferred artifact regeneration path for local verification:
   - `docker compose -f infra/docker-compose.yml exec -T app sh -lc "DOCMAP_ADMIN_BOUNDARIES_REFRESH_SOURCE=0 python -m services.analytics.scripts.rebuild_admin_boundaries"`
   - Restart presentation after generation:
     - `docker compose -f infra/docker-compose.yml restart presentation`
3. Run the benchmark:
   - `python services/presentation/scripts/measure_phase_f_ui_performance.py --base-url http://localhost:8080`
4. Review output JSON:
   - current metrics file:
     - `docs/qa/baked_interactive_geometry_phase_f_current_2026-04-20.json`
   - comparison file:
     - `docs/qa/baked_interactive_geometry_phase_f_comparison_2026-04-20.json`
5. Gate conditions:
   - `summary.minimum_5x_met` must be `true` to claim minimum target achieved.
   - `summary.stretch_20x_met` records whether stretch target is achieved.
   - If `stretch_20x_met` is `false`, use `limiting_factors_for_20x` to document precise blockers.

Phase F harness guardrails:
- fails fast when `/api/map/baked/manifest` is unavailable
- fails fast when initial load traffic indicates old normal-view live boundaries behavior (`/api/map/boundaries`)
- records both encoded payload bytes (`content-length`) and decoded response body bytes

## Presentation Runtime Phase A Verification

Use presentation logs in a second shell:
`docker compose -f infra/docker-compose.yml logs -f presentation`

Expected hot-path log families:
- `presentation.api_request`
- `presentation.locations_repo_fetch`
- `presentation.boundaries_repo_fetch`
- `presentation.resolve_location_for_documents`
- `presentation.location_documents_repo_fetch`
- `presentation.document_locations_repo_fetch`
- `presentation.search_repo_fetch`

Startup timing:
1. Open `http://localhost:8080/`.
2. In browser console, record:
   - `presentation.performance.first_meaningful_render_ms`
   - `presentation.performance.boundaries_ready_ms`
3. In presentation logs, confirm at least one `presentation.api_request route=/api/map/locations`.
4. In presentation logs, confirm baked requests are logged with:
   - `route=/api/map/baked/manifest`
   - `route=/api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt`
5. In presentation logs, confirm `/api/map/boundaries` appears only for explicit selected/highlight requests.

Boundary request checks by interaction:
1. Prefer:
   `docker compose -f infra/docker-compose.yml exec -T app pytest -q tests/test_presentation_browser_regression.py -k baked_normal_view_and_explicit_live_overlays`
2. If browser automation is unavailable, use devtools Network and pan the map through one representative low-zoom and one representative regional move.
3. Confirm normal pan/zoom does not call `/api/map/boundaries`, while explicit selection/highlight still does.

Location-documents timing:
1. Pick a populated location id from:
   `Invoke-RestMethod -Uri 'http://localhost:8080/api/map/locations' | Select-Object -First 5 location_id,name,document_count`
2. Measure the endpoint directly, for example:
   ```powershell
   $uri = 'http://localhost:8080/api/map/location/{location_id}/documents?limit=80&offset=0'
   1..3 | ForEach-Object {
     $sw = [System.Diagnostics.Stopwatch]::StartNew()
     $resp = Invoke-WebRequest -UseBasicParsing -Uri $uri -TimeoutSec 60
     $sw.Stop()
     [pscustomobject]@{Ms=[math]::Round($sw.Elapsed.TotalMilliseconds,2); Bytes=$resp.RawContentLength; Status=$resp.StatusCode}
   }
   ```
3. In presentation logs, record:
   - `presentation.api_request route=/api/map/location/{location_id}/documents`
   - `presentation.resolve_location_for_documents`
   - `presentation.location_documents_repo_fetch`

Search timing:
1. Measure with representative text and SCP-number queries, for example:
   ```powershell
   $uri = 'http://localhost:8080/api/search?q=paris&limit=5'
   1..3 | ForEach-Object {
     $sw = [System.Diagnostics.Stopwatch]::StartNew()
     $resp = Invoke-WebRequest -UseBasicParsing -Uri $uri -TimeoutSec 60
     $sw.Stop()
     [pscustomobject]@{Ms=[math]::Round($sw.Elapsed.TotalMilliseconds,2); Bytes=$resp.RawContentLength; Status=$resp.StatusCode}
   }
   ```
2. Repeat with an SCP number query such as `scp-173`.
3. In presentation logs, record:
   - `presentation.api_request route=/api/search`
   - `presentation.search_repo_fetch`

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
