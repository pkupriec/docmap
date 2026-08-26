# Chunked Boundary Delivery Plan

Date: 2026-04-14
Owner: Presentation runtime team
Status: Proposed next implementation task

## 1. Objective

Keep full stored geometry canonical while making polygon delivery behave more like a modern slippy-map system.

Target outcomes:
- no correctness regression in boundary geometry or feature membership
- avoid near-world polygon fetches during ordinary startup and low-zoom navigation
- reduce repeated viewport refetch churn from tiny pan/zoom changes
- keep explicit selected/highlighted polygon reveal working
- make polygon delivery scale with visible map area instead of raw viewport float changes

Primary idea:
- stop treating boundary delivery as one monolithic viewport query
- move toward chunked or vector-tile-style delivery
- fetch only spatial chunks intersecting the current visible map plus a small safety margin
- merge chunk results client-side while keeping full geometry canonical at rest

## 2. Validated Current State (Code-Backed)

Validated from implementation on 2026-04-14:
- frontend now waits for viewport before boundary requests
- backend supports `bbox`, `ranks`, `selected_location_id`, and `highlighted_location_ids`
- backend serves full stored geometry only
- low zoom still can produce very large broad-rank responses for wide world views
- cache keys currently depend on raw request shape, including raw float bbox values
- frontend still refetches whole scoped sets when selection/focus changes

Current heavy paths:
- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/api.ts`
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`

## 3. Scope

In scope:
- presentation backend/frontend delivery model changes
- cache and request-shape changes needed for spatial chunking
- chunk merge behavior for viewport and explicit focus polygons
- deterministic ordering and stable render behavior
- docs and verification updates

Out of scope:
- changing canonical geometry source of truth
- geometry simplification/decimation
- replacing MapLibre/Deck renderer by default
- control plane or analytics write-behavior redesign beyond owned geometry metadata/index support

## 4. Design Principles

1. Full geometry remains canonical.
   - no coordinate simplification for standard presentation delivery
   - no low-detail geometry artifact path reintroduced

2. Deliver less by partitioning, not by degrading.
   - reduce delivered scope using spatial chunks/tiles
   - preserve exact stored geometry for included features

3. Stable chunk identity matters.
   - request shapes should snap to stable chunk ids
   - nearby pans should reuse cached chunk responses

4. Explicit focus remains additive.
   - selected/highlighted polygons must still load even outside current visible chunks

5. Frontend rendering must stay flicker-free.
   - keep old chunk-backed polygons visible until replacement chunk set is ready
   - stale async responses must not overwrite newer state

## 5. Candidate Delivery Model

Preferred direction:
- introduce a chunked boundaries API surface while keeping `/api/map/boundaries` available
- derive chunk ids from map zoom band plus normalized world-space or lon/lat grid partitioning
- backend returns polygons for specific chunk ids and ranks
- frontend requests only intersecting chunks for the current view

Two acceptable implementations:

### Option A - Chunk Id API (preferred)

Add a new request shape such as:
- `chunk_ids={csv}`
- `ranks={csv}`
- `selected_location_id={uuid}`
- `highlighted_location_ids={uuid,...}`
- `lite={bool}`

Frontend responsibilities:
- compute chunk ids from viewport plus configurable margin
- diff current vs required chunk set
- fetch only missing chunks
- evict stale far-away chunks conservatively

Backend responsibilities:
- map chunk ids to deterministic spatial filters
- return only features intersecting those chunks plus explicit inclusions
- keep ordering stable within each chunk response

### Option B - Quantized Viewport API (acceptable stepping stone)

If chunk ids are too large a jump for one session:
- quantize bbox requests into stable spatial buckets
- cache by quantized bucket ids instead of raw float bounds
- split explicit focus fetches from viewport fetches

This is weaker than full chunking but moves the system toward it.

## 6. Recommended Phase Breakdown

### Phase A - Request Model Refactor

Purpose: separate viewport chunk loading from explicit focus loading.

Tasks:
1. Split frontend boundary state into:
   - viewport chunk request state
   - explicit focus request state
   - merged feature store by `location_id`
2. Keep selected/highlighted fetches additive instead of forcing full viewport reloads.
3. Add request versioning per request class.

Acceptance:
- changing selection does not trigger full viewport boundary reload
- explicit polygons persist independently from viewport chunk refreshes

### Phase B - Stable Spatial Chunking

Purpose: replace raw viewport float request shapes with stable chunk identities.

Tasks:
1. Define chunk grid scheme for current map zoom bands.
2. Compute chunk ids deterministically from viewport plus margin.
3. Update backend cache to key by normalized chunk ids and ranks.
4. Ensure chunk ordering is deterministic for identical chunk sets.

Acceptance:
- nearby pans reuse chunk cache instead of missing on tiny bbox changes
- identical chunk-id requests are cache-stable

### Phase C - Backend Chunk Read Path

Purpose: make boundary reads proportional to chunk coverage.

Tasks:
1. Add backend repository filtering by chunk ids or chunk-derived bounds.
2. If needed, add migration-backed chunk metadata/index support for `bi_admin_boundaries`.
3. Support polygons intersecting multiple chunks without duplicate emission.
4. Preserve explicit inclusion outside viewport chunks.

Acceptance:
- viewport delivery scales with intersecting chunks
- duplicate polygons are not emitted when they cross chunk boundaries

### Phase D - Frontend Chunk Cache + Merge

Purpose: avoid replacing the whole polygon set on every move.

Tasks:
1. Cache chunk payloads client-side by chunk id + rank shape.
2. Merge chunk results into one rendered feature map keyed by `location_id`.
3. Keep loaded chunks visible during incremental fetches.
4. Prune old chunks using a conservative retention strategy.

Acceptance:
- pan/zoom causes incremental add/remove behavior instead of full-set replacement
- no visible flicker during ordinary movement

### Phase E - Verification and Tuning

Purpose: verify practical improvement and tune chunk sizing.

Tasks:
1. Measure chunk counts and payload sizes by zoom band.
2. Measure request frequency during pan/zoom.
3. Validate selection/highlight correctness across chunk boundaries.
4. Tune viewport margin and chunk granularity using actual logs.

Acceptance:
- startup and ordinary pan/zoom no longer request near-world polygon sets for broad ranks
- request count and payload size are materially lower than raw viewport-scope delivery

## 7. Schema and Repository Guidance

Preferred backend support:
- keep reading from `bi_admin_boundaries`
- add derived metadata only if needed to support fast chunk intersection

Possible metadata additions:
- chunk-cover membership table or materialized mapping
- coarse grid columns
- retained envelope columns as a first-stage prefilter

Constraints:
- startup-compatible migrations only
- presentation remains read-only
- analytics remains owner of canonical geometry content

## 8. Frontend State Guidance

Recommended state model:
- `locations`: loaded once
- `viewportChunkIds`: derived from viewport + zoom band + margin
- `loadedBoundaryChunks`: chunk payload cache
- `explicitBoundaryFeatures`: selected/highlighted payload cache
- `renderedBoundaryFeatures`: merged location-id keyed map

Recommended request flow:
1. viewport arrives
2. derive chunk ids
3. diff against loaded chunk cache
4. fetch missing chunks
5. merge into rendered feature map
6. fetch explicit focus polygons separately when needed
7. render merged result

## 9. Deliverables

Required code deliverables:
- chunked or quantized boundary delivery model
- separate explicit focus polygon loading path
- backend cache keyed by stable chunk/bucket identity
- frontend chunk merge cache

Required docs updates:
- `docs/presentation/PRESENTATION_API_SPEC.md`
- `docs/presentation/PRESENTATION_DATA_CONTRACT.md`
- `docs/presentation/PRESENTATION_UX_SPEC.md`
- `docs/operations/VERIFICATION.md`
- relevant QA checklist/test-case docs

## 10. Verification Protocol

Capture:
- chunk ids requested for representative zoom levels
- features per chunk and total merged visible features
- payload size per chunk request
- number of boundary requests during pan/zoom
- whether selection/highlight causes only explicit fetches
- whether polygons remain visible during chunk refresh

Required scenarios:
1. Startup at low zoom:
   - no near-world admin-region fetch
   - only broad-rank chunks requested
2. Regional pan:
   - only newly intersecting chunks fetched
3. Zoom-in:
   - narrower ranks/chunks added incrementally
4. Selection outside viewport:
   - explicit polygon fetched without widening viewport chunk scope
5. Search highlight:
   - highlighted polygons appear without full viewport replacement

## 11. Risks and Mitigations

Risk: chunk ids too coarse still produce oversized payloads.
Mitigation: tune chunk size by zoom band and verify with concrete counts.

Risk: chunk boundaries create duplicate polygon delivery.
Mitigation: dedupe client and/or backend by `location_id`.

Risk: explicit focus merge becomes inconsistent with viewport chunk state.
Mitigation: keep explicit cache as a separate additive source of truth.

Risk: implementation becomes too ambitious for one session.
Mitigation: allow quantized viewport buckets as a stepping stone, but do not reintroduce low-detail geometry.

## 12. Execution Order

1. Phase A - Request Model Refactor
2. Phase B - Stable Spatial Chunking
3. Phase C - Backend Chunk Read Path
4. Phase D - Frontend Chunk Cache + Merge
5. Phase E - Verification and Tuning

Do not start any renderer replacement work before this delivery-model work is implemented and measured.
