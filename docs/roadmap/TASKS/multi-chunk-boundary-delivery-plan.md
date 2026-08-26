# Multi-Chunk Boundary Delivery Plan

Date: 2026-04-14
Owner: Presentation runtime team
Status: Proposed next implementation task

## 1. Objective

Move the presentation runtime from single quantized viewport-bucket requests to a multi-chunk request set with client-side chunk retention and pruning.

Target outcomes:
- keep full stored geometry canonical
- stop replacing the whole viewport polygon set on each bucket change
- fetch only newly needed chunks during ordinary pan/zoom
- retain already loaded visible polygons while adjacent chunks load
- keep explicit selected/highlighted polygon loading additive and independent
- prove with browser-level regression coverage that selection/highlight does not trigger viewport chunk reloads

Primary idea:
- replace one `viewport_bucket` request with a deterministic set of chunk ids
- cache chunk payloads client-side by chunk id plus rank shape
- diff required vs loaded chunk sets on viewport changes
- fetch only missing chunks and conservatively prune far-away chunks
- keep explicit-focus polygons in a separate additive cache keyed by `location_id`

## 2. Validated Current State (Code-Backed)

Validated from implementation on 2026-04-14:
- frontend boundary flow is split into viewport loading and explicit focus loading
- backend supports stable quantized `viewport_bucket` identities as a stepping stone
- backend cache keys normalize around canonical request shapes
- backend suppresses duplicate polygons for the same `location_id`
- frontend merges viewport and explicit boundary payloads by `location_id`
- stale async viewport and explicit responses are version-gated

Current remaining gap:
- viewport loading is still one quantized bucket request at a time
- pan/zoom across bucket boundaries still replaces the full viewport-scoped payload rather than diffing chunks
- no browser-level regression currently proves chunk reuse or focus-only request isolation

Current heavy paths:
- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/api.ts`
- `services/presentation/frontend/src/types.ts`
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`

## 3. Scope

In scope:
- presentation frontend/backend chunk delivery model
- chunk-id request contract and normalization
- client-side chunk cache, retention, merge, and pruning
- browser-level regression coverage for request behavior
- docs and verification updates

Out of scope:
- geometry simplification/decimation
- renderer replacement
- analytics ownership changes to canonical geometry
- unrelated frontend refactors or styling cleanup

## 4. Design Principles

1. Full geometry remains canonical.
   - only full stored geometry may be served
   - no reduced-detail or simplified polygon path

2. Reduce delivery by partitioning, not degrading.
   - smaller request scope comes from chunking
   - chunk membership may duplicate spatial coverage, but emitted features must still dedupe by `location_id`

3. Viewport and explicit focus stay separate.
   - chunk loading is viewport-driven
   - selected/highlighted polygons load additively
   - focus-only changes must not invalidate viewport chunk cache

4. Rendering stays flicker-free.
   - keep currently rendered polygons until successor chunk state is ready
   - do not blank the polygon layer between chunk refreshes

5. Request shapes stay deterministic.
   - identical viewport/rank conditions derive identical sorted chunk ids
   - identical chunk-id requests must produce deterministic ordering and cache hits

## 5. Target Delivery Model

Preferred direction:
- extend `/api/map/boundaries` to accept `chunk_ids={csv}` as the primary viewport-scoped request shape
- keep `viewport_bucket` only as a compatibility stepping stone or fallback

Target query parameters:
- `lite={bool}`
- `rank_filter={default|all}` optional compatibility selector
- `ranks={csv}`
- `chunk_ids={csv}` preferred viewport-scoped request shape
- `selected_location_id={uuid}`
- `highlighted_location_ids={uuid,...}`

Rules:
- `chunk_ids` and `viewport_bucket` should be mutually exclusive when both are supported
- chunk ids must be normalized, deduped, and sorted canonically
- backend responses must not emit duplicate polygons for the same `location_id`

## 6. Recommended Phase Breakdown

### Phase A - Chunk Id Contract

Purpose: replace single viewport-bucket loading with a deterministic chunk-id request set.

Tasks:
1. Define a chunk grid scheme by zoom band.
2. Derive a sorted chunk id set from viewport plus safety margin.
3. Add backend API parsing/validation for `chunk_ids`.
4. Normalize cache keys around sorted canonical chunk ids.
5. Keep `viewport_bucket` support only as fallback/compatibility if needed during transition.

Acceptance:
- identical viewports derive identical sorted chunk id sets
- nearby float churn that stays within the same chunk set reuses cache
- chunk-id request parsing and normalization are covered by tests

### Phase B - Backend Chunk Read Path

Purpose: make backend reads proportional to intersecting chunk coverage.

Tasks:
1. Map chunk ids to deterministic bounds on the backend.
2. Read polygons intersecting any requested chunk plus explicit selected/highlighted ids.
3. Preserve deterministic ordering for identical chunk-id sets.
4. Deduplicate emitted polygons by `location_id`.
5. Keep full geometry untouched in the response.

Acceptance:
- chunk-id requests return only intersecting polygons plus explicit inclusions
- duplicate `location_id` emission is prevented even when shapes intersect multiple chunks
- warm identical chunk-id requests hit cache

### Phase C - Frontend Chunk Cache, Retention, and Pruning

Purpose: stop replacing the whole viewport payload when only some chunks change.

Tasks:
1. Replace single viewport-boundary state with:
   - `requiredViewportChunkIds`
   - `loadedViewportChunks`
   - `renderedViewportFeatures`
2. Diff required vs loaded chunk ids on viewport changes.
3. Fetch only missing chunks for the current rank band.
4. Keep already loaded visible chunks rendered while missing chunks load.
5. Prune stale far-away chunks conservatively without dropping still-required chunks.
6. Merge viewport chunks plus explicit-focus features client-side by `location_id`.

Acceptance:
- ordinary pan/zoom fetches only newly intersecting chunks
- already loaded chunks remain visible during incremental updates
- selection/highlight changes do not cause viewport chunk refetch

### Phase D - Browser Regression Coverage

Purpose: prove request behavior and interaction stability at browser level.

Tasks:
1. Add browser-level regression coverage for initial load, pan, zoom, and selection/highlight flows.
2. Capture boundary requests from the browser/network layer.
3. Assert that:
   - pan/zoom only requests missing/new chunks
   - chunk ids are reused across nearby pans
   - selection/highlight triggers only explicit polygon fetches
   - viewport chunk requests are not reissued solely due to selection/highlight changes
4. Keep assertions stable and deterministic enough for CI/local repro.

Acceptance:
- regression test fails if viewport chunk reloads are reintroduced by focus-only changes
- regression test fails if nearby pan reverts to whole-set reload behavior

## 7. Backend Guidance

Preferred backend support:
- continue reading from `bi_admin_boundaries`
- use existing envelope columns as prefilter
- derive chunk bounds in request-time code rather than introducing write-side ownership changes unless needed

Implementation notes:
- chunk ids may encode `band:x:y` or an equivalent deterministic grid address
- if one request covers many chunk ids, repository filtering may translate them into a bounded disjunction of spatial envelope clauses
- ordering should stay stable:
  - rank priority first
  - `location_id` second

## 8. Frontend State Guidance

Recommended state model:
- `locations`: loaded once
- `viewportChunkRequest`: derived from viewport + zoom band + margin
- `loadedViewportChunks`: cache keyed by chunk id + rank shape
- `explicitBoundaryFeatures`: additive cache keyed by explicit request shape
- `renderedBoundaryFeatures`: merged feature map by `location_id`

Recommended request flow:
1. viewport arrives
2. derive required chunk ids
3. compare against loaded chunk cache
4. fetch only missing chunk ids
5. merge chunk payloads into rendered feature map
6. prune stale chunks conservatively
7. fetch explicit focus polygons independently when needed

## 9. Deliverables

Required code deliverables:
- chunk-id request contract
- backend chunk-id read/filter path
- frontend chunk diff/cache/retention flow
- browser-level regression coverage for request behavior

Required docs updates:
- `docs/presentation/PRESENTATION_API_SPEC.md`
- `docs/presentation/PRESENTATION_DATA_CONTRACT.md`
- `docs/presentation/PRESENTATION_UX_SPEC.md`
- `docs/operations/VERIFICATION.md`
- relevant QA checklist/test-case docs

## 10. Verification Protocol

Capture:
- chunk ids requested for representative zoom levels
- number of boundary requests during startup, pan, zoom, and focus changes
- features per chunk and total merged visible features
- whether pan/zoom fetches only newly needed chunks
- whether selection/highlight triggers only explicit fetches
- whether currently visible polygons stay rendered during refresh

Required scenarios:
1. Initial load:
   - first viewport derives deterministic chunk ids
   - only missing chunks are fetched
2. Nearby pan within partial overlap:
   - overlapping chunks are reused
   - only newly intersecting chunks are fetched
3. Zoom transition:
   - rank band/chunk set changes deterministically
   - obsolete chunks are pruned conservatively
4. Selection outside viewport:
   - explicit polygon loads without widening viewport chunk scope
5. Search highlight:
   - highlighted polygons appear without triggering viewport chunk reload

## 11. Risks and Mitigations

Risk: chunk ids create too many backend clauses per request.
Mitigation: tune chunk size by zoom band and cap the viewport margin conservatively.

Risk: chunk pruning causes visible polygon popping.
Mitigation: prune only after replacement chunk state is ready and keep still-required chunks until handoff completes.

Risk: chunk overlap causes duplicate feature emission.
Mitigation: preserve backend and client dedupe by `location_id`.

Risk: browser regression checks are flaky.
Mitigation: assert on normalized request shapes and ordered network events rather than timing-sensitive rendering details.

## 12. Execution Order

1. Phase A - Chunk Id Contract
2. Phase B - Backend Chunk Read Path
3. Phase C - Frontend Chunk Cache, Retention, and Pruning
4. Phase D - Browser Regression Coverage

Do not broaden into renderer replacement or geometry simplification work during this task.
