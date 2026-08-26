# Full Geometry Incremental Delivery Plan

Date: 2026-04-14
Owner: Presentation runtime team
Status: Approved for implementation

## 1. Objective

Preserve full stored boundary geometry while eliminating all-runtime "load everything" behavior that currently overwhelms the browser.

Target outcomes:
- no `geometry_detail=low` mode in presentation API or frontend
- no initial full-world polygon load on startup
- startup first meaningful render (points visible): <= 1.0s after app load on local stack
- boundary overlay for current viewport/rank scope usable: <= 1.5s after locations render
- map interactions remain responsive during pan/zoom/selection
- browser must not allocate polygon buffers for unseen or currently irrelevant geometry

## 2. Validated Current State (Code-Backed)

Validated from implementation on 2026-04-14:
- frontend currently fetches `/api/map/boundaries` during startup from `services/presentation/frontend/src/App.tsx`
- frontend and backend still support `geometry_detail=low|full`
- backend returns `FeatureCollection` assembled from `bi_admin_boundaries`
- `bi_admin_boundaries` currently contains full stored geometry for all matched polygon targets
- full-world default boundary response can trigger Deck/PathLayer allocation failure in browser when all polygons are loaded together

Current heavy paths:
- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/api.ts`
- `services/presentation/frontend/src/types.ts`
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`

## 3. Scope

In scope:
- presentation backend and frontend contract changes
- removal of reduced-geometry delivery mode from presentation API
- viewport/rank-scoped boundary fetching
- on-demand loading for selected/highlighted polygons
- deterministic cache behavior for scoped boundary requests
- docs and verification updates

Out of scope:
- analytics geometry generation changes beyond continuing to populate `bi_admin_boundaries`
- control plane changes
- geocoder semantics changes
- write behavior in presentation runtime

## 4. Design Principles

1. Full geometry remains canonical.
   - Presentation must serve full stored geometry only.
   - No alternate low-detail artifact path.
   - No runtime geometry decimation/simplification path in backend.

2. Render less, not worse.
   - Limit delivery by viewport, rank, and explicit user focus.
   - Do not reduce coordinates to make payload smaller.

3. Keep map startup non-blocking.
   - Locations load first.
   - Boundary fetches begin only after viewport is known.

4. Request only what can currently matter.
   - low zoom: broad polygon ranks only
   - higher zoom: narrower polygon ranks
   - selected/highlighted targets can be fetched explicitly even when outside default current rank scope

5. Preserve deterministic behavior.
   - identical query shape + DB state returns deterministic ordering and content
   - cache keys must include all request-shaping params

## 5. Target API Shape

Replace the current "detail reduction" selector with spatial/interaction selectors.

Primary endpoint:
- `GET /api/map/boundaries`

Required query parameters/behavior:
- `lite={bool}` keeps current minimal/full-properties behavior
- `rank_filter={default|all}` may remain temporarily for compatibility, but default runtime path should use explicit rank lists instead
- `ranks={csv}` optional explicit list of requested polygon ranks
- `bbox={west,south,east,north}` optional viewport bounds in WGS84
- `selected_location_id={uuid}` optional explicit inclusion target
- `highlighted_location_ids={uuid,uuid,...}` optional explicit inclusion targets
- `limit={int}` optional defensive cap for explicit target fetches if needed

Required removals:
- remove `geometry_detail`
- remove all low/full geometry branching from presentation runtime

Response:
- `FeatureCollection`
- full stored geometry only
- features must be limited to the requested spatial/rank/explicit inclusion scope

## 6. Boundary Fetch Strategy

### Phase A - Contract Cutover and API Cleanup

Purpose: remove low-detail mode from the presentation contract and replace it with explicit query shaping.

Tasks:
1. Remove `GeometryDetail` type and `geometry_detail` parameter from:
   - backend API
   - backend repository
   - frontend request types/helpers
   - tests/docs
2. Introduce request-shaping params for:
   - `bbox`
   - `ranks`
   - `selected_location_id`
   - `highlighted_location_ids`
3. Keep `lite` behavior unchanged.
4. Add validation rules:
   - bbox must parse into four finite values
   - bbox longitude wrap handling must be explicit
   - ranks must normalize `region -> admin_region`
   - explicit ids must be valid UUIDs
5. Update cache key composition to include the new query shape.

Acceptance:
- no `geometry_detail` references remain in live presentation code path
- `/api/map/boundaries` can return scoped subsets by bbox/ranks/explicit ids
- tests cover request parsing and cache-key behavior

### Phase B - Repository Spatial Filtering

Purpose: ensure backend returns only polygons relevant to the current viewport/rank scope.

Tasks:
1. Add repository filtering over `bi_admin_boundaries` using polygon bbox metadata derived from geometry.
2. Choose one implementation:
   - preferred: compute geometry envelope in SQL from stored GeoJSON and filter server-side
   - fallback: add persisted bbox columns to `bi_admin_boundaries` through startup migration and populate from stored geometry
3. Support antimeridian-aware viewport behavior.
4. Always include explicitly requested selected/highlighted location ids even if they fall outside viewport bbox.
5. Preserve deterministic ordering:
   - broad-to-narrow rank order
   - stable location_id ordering within rank

Acceptance:
- viewport-scoped request returns only intersecting polygons plus explicit inclusions
- full-world request remains possible for diagnostics but is not used by default UI
- warm scoped boundary requests are materially smaller than current all-world full-geometry path

### Phase C - Frontend Incremental Boundary Loading

Purpose: fetch boundaries only after the map knows what the user is looking at.

Tasks:
1. Remove startup boundary fetch from app bootstrap.
2. Wait for initial map viewport from `MapView`.
3. Trigger boundary fetches only when:
   - viewport becomes available
   - zoom crosses rank-band threshold
   - selected location changes
   - highlighted search locations change
4. Debounce viewport-driven fetches to avoid network churn during pan/zoom.
   - suggested starting debounce: 150-250ms after move end
5. Keep previous polygons visible during in-flight refresh to prevent flicker.
6. Distinguish status states:
   - no viewport yet
   - loading scoped boundaries
   - boundaries ready
   - boundaries unavailable

Acceptance:
- app no longer requests boundaries before viewport is known
- panning and zooming cause bounded, debounced scoped refetches
- no blank-map flicker during ordinary navigation

### Phase D - Rank Banding by Zoom

Purpose: avoid rendering rank classes that are not useful at the current scale.

Default rank-band policy:
- zoom `< 3.2`: `continent,country,admin_region,ocean`
- zoom `>= 3.2` and `< 6.0`: `country,admin_region,ocean`
- zoom `>= 6.0`: `admin_region,city`

Tasks:
1. Encode frontend zoom-to-rank-band mapping in one place.
2. Use explicit `ranks` requests rather than relying on `rank_filter=default`.
3. Preserve explicit inclusion behavior:
   - selected location polygon may be requested even if its rank is outside current band
   - highlighted search locations may be requested even if outside current band
4. Ensure points fallback remains available when no polygon is loaded for a location.

Acceptance:
- low zoom no longer asks for city polygons
- high zoom can request city polygons without loading the entire world
- clicking/searching a location can still reveal its polygon when available

### Phase E - On-Demand Explicit Polygon Fetch

Purpose: support interaction-driven polygon reveal without broadening the viewport fetch too far.

Tasks:
1. When a location is selected from map/search/panel, ensure its polygon is fetched by `selected_location_id`.
2. When search results highlight locations, include `highlighted_location_ids`.
3. Merge explicit polygons with viewport polygons client-side by `location_id`.
4. Expire stale explicit inclusions when selection/highlight is cleared.

Acceptance:
- selected polygon can appear even when outside normal viewport rank fetch policy
- search-highlighted locations can show polygons without widening global fetch scope

## 7. Repository and Schema Guidance

Preferred backend implementation:
- continue reading from `bi_admin_boundaries`
- add bbox filtering close to data

Recommended options, in order:
1. Add persisted envelope columns to `bi_admin_boundaries`:
   - `min_lon`
   - `min_lat`
   - `max_lon`
   - `max_lat`
2. Populate these in startup migration / analytics boundary-write path.
3. Query by envelope intersection first, then return stored feature JSON untouched.

Why this is preferred:
- avoids reparsing all GeoJSON rows per request just to discard most of them
- keeps full geometry canonical
- keeps request-time work proportional to visible scope

If schema changes are needed:
- update `services/common/migrations.py`
- keep startup migration compatibility for existing DBs
- update tests to cover migration-backed behavior

## 8. Frontend State Model Guidance

Recommended state separation:
- `locations`: all points, loaded once
- `boundaryViewportRequest`: derived from viewport + zoom rank band
- `boundaryExplicitRequest`: derived from selection/highlight state
- `boundaryFeatures`: merged feature map by `location_id`

Recommended request flow:
1. map loads
2. locations load
3. viewport reported
4. derive rank band from zoom
5. fetch viewport polygons
6. if selected/highlighted ids exist, fetch explicit polygons or include them in same request
7. merge into `boundaryFeatures`
8. `MapView` renders polygons only for currently loaded location ids

Recommended anti-jank controls:
- debounce viewport requests
- ignore stale async responses using request token/versioning
- avoid clearing polygon records until replacement data is ready

## 9. Deliverables

Required code deliverables:
- new scoped boundaries API contract without `geometry_detail`
- backend spatial filtering path for `bi_admin_boundaries`
- frontend viewport/rank/on-demand boundary loading
- zoom-band rank policy
- boundary merge/cache behavior for viewport + explicit inclusions

Required docs updates:
- `docs/presentation/PRESENTATION_API_SPEC.md`
- `docs/presentation/PRESENTATION_DATA_CONTRACT.md`
- `docs/presentation/PRESENTATION_UX_SPEC.md` if visible loading behavior changes
- `docs/operations/VERIFICATION.md`
- `docs/qa/presentation_requirements_checklist.md`
- `docs/qa/presentation_test_cases.md`

## 10. Verification Protocol

For each implemented phase, capture:
- startup render timing
- first viewport boundary request timing
- payload size by request shape
- feature counts by request shape
- browser console health during boundary rendering
- pan/zoom request frequency
- selection/highlight polygon inclusion correctness

Required verification scenarios:
1. Initial load:
   - locations visible before any polygons
   - first viewport-scoped polygon fetch succeeds
2. Low zoom:
   - only broad ranks requested
   - no city polygon world-load
3. Medium zoom:
   - admin/country polygons scoped to current viewport
4. High zoom:
   - city polygons only for visible area
5. Search highlight:
   - highlighted location polygon appears even if not part of default rank band
6. Selection:
   - selected location polygon persists while panning
7. Interaction:
   - no browser allocation failures
   - no Deck polygon init crash in standard usage

## 11. Risks and Mitigations

Risk: viewport bbox filtering based on geometry envelope misses antimeridian-spanning shapes.
Mitigation: explicitly handle wrapped longitude requests and test ocean/large polygon cases.

Risk: selected location polygon disappears when it leaves viewport.
Mitigation: explicit inclusion path by selected/highlighted ids.

Risk: frequent pan/zoom causes excessive refetch churn.
Mitigation: debounce requests and ignore stale responses.

Risk: envelope filtering still returns too many broad-rank polygons in huge world views.
Mitigation: combine bbox filtering with zoom-based rank bands and optional hard result caps for diagnostics-only paths.

Risk: removing `geometry_detail` breaks existing verification/docs/tests.
Mitigation: update contract docs and replace old low/full tests with viewport/rank-scope tests in the same change set.

## 12. Execution Order

1. Phase A - Contract Cutover and API Cleanup
2. Phase B - Repository Spatial Filtering
3. Phase C - Frontend Incremental Boundary Loading
4. Phase D - Rank Banding by Zoom
5. Phase E - On-Demand Explicit Polygon Fetch

Do not ship Phase C or later without Phase B, because frontend incremental loading without backend spatial filtering still allows oversized full-geometry fetches.

