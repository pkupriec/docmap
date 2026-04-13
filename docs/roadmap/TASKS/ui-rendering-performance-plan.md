# UI Rendering Performance Implementation Plan

Date: 2026-03-29
Owner: Presentation runtime team
Status: Approved for implementation

## 1. Objective

Optimize presentation UI so map interaction is fast and startup is not blocked by heavyweight boundary geometry.

Target outcomes:
- first meaningful render (points visible): <= 1.0s after app load (local stack)
- boundary overlay usable: <= 2.0s after first render (non-blocking)
- default boundary payload decoded size: <= 5 MB
- hover/click interaction p95: <= 16ms

## 2. Validated Current State (Code-Backed)

Validated from implementation on 2026-03-29:
- startup is blocked by `Promise.all([fetchLocations(), fetchBoundaries()])` in frontend
- boundaries are fetched from `/api/map/boundaries?lite=1` during startup
- backend rebuilds boundary JSON per request from DB rows (no in-process cache)
- map pulse animation updates React state every 50ms and triggers Deck layer rebuild
- click resolution includes O(N polygons) point-in-polygon fallback scan

Current heavy paths:
- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`

## 3. Scope

In scope:
- presentation backend and frontend performance work only
- API compatibility-preserving extensions
- deterministic payload reduction and interaction optimization

Out of scope:
- control plane behavior changes
- pipeline stage semantics outside boundary artifact generation
- auth/deployment hardening

## 4. Implementation Phases

## Phase A - Fast UX Unblock (P0)

Purpose: remove startup blocking and avoid repeated heavy boundary rebuilds.

Tasks:
1. Decouple startup load order in frontend.
   - Load locations first.
   - Set UI to ready after locations load.
   - Fetch boundaries in background and hydrate map when available.
   - Preserve graceful error state for boundaries-only failure.
2. Add in-process cache for boundaries in presentation backend.
   - Cache keys by request shape (`minimal`, later filters/detail).
   - TTL: 10 minutes.
   - Cache invalidation on process restart (acceptable).
3. Add lightweight timing logs around boundary generation path.

Acceptance:
- map points are visible before boundaries finish loading
- repeated `/api/map/boundaries` requests avoid repeated parse/rebuild within TTL

## Phase B - Default Payload Reduction (P1)

Purpose: make default payload small enough for responsive interactions.

Tasks:
1. Extend boundaries API with optional filters:
   - `rank_filter=default|all` (default: `default`)
   - `geometry_detail=low|full` (default: `low`)
2. Define default rank set:
   - include: `city`, `admin_region`/`region`, `country`, `continent`, `ocean`
   - exclude: `admin_level_*` and specialty ranks from default path
3. Introduce low-detail geometry artifacts (precomputed, deterministic).
   - generated in analytics/offline step
   - versioned artifact naming for reproducibility
4. Frontend consumes default reduced payload unless explicitly overridden.

Acceptance:
- decoded default boundary payload <= 5 MB
- coordinate count reduced by >= 70% vs current default path

## Phase C - Delivery Path Stabilization (P2)

Purpose: remove per-request heavy assembly from standard UI traffic.

Tasks:
1. Serve prebuilt boundary artifacts for standard boundary variants.
2. Attach long-lived cache headers and validators:
   - `Cache-Control`
   - `ETag`
3. Keep API endpoint as selector wrapper over artifact variants.

Acceptance:
- standard boundary requests no longer perform DB row iteration + JSON assembly
- warm local fetch for boundaries <= 300ms

## Phase D - Interaction Cost Optimization (P3)

Purpose: eliminate render jank and click/hover spikes under load.

Tasks:
1. Pulse optimization:
   - avoid full layer recreation on pulse ticks
   - isolate pulse to minimal layer prop updates or separate overlay
2. Click optimization:
   - remove global polygon scan as default fallback
   - add candidate reduction (bbox/grid index) before point-in-polygon
3. Recompute minimization:
   - stabilize memoization keys for polygon/point transforms
   - keep boundary index maps outside hot interaction state
4. Card panel cost controls:
   - reduce initial card page size
   - narrow thumbnail prefetch margin
   - add card list virtualization if needed by profiling

Acceptance:
- click/hover p95 <= 16ms on representative local dataset
- no visible pulse-driven frame drops during search/hover/click activity

## 5. Deliverables

Required code deliverables:
- frontend startup sequencing and boundary background load
- backend boundary response cache
- API filter/detail parameters and contract updates
- artifact-based boundary serving path
- map interaction optimizations

Required docs updates:
- `docs/presentation/PRESENTATION_API_SPEC.md`
- `docs/presentation/PRESENTATION_DATA_CONTRACT.md`
- `docs/presentation/PRESENTATION_UX_SPEC.md` (if visible behavior changes)
- `docs/operations/VERIFICATION.md` with repeatable perf checks

## 6. Verification Protocol

Collect before/after for each phase:
- `/api/map/boundaries` payload bytes (encoded + decoded)
- endpoint latency (cold/warm)
- first meaningful render timestamp
- boundary-ready timestamp
- hover and click handler p95 durations

Add repeatable verification script(s) to report:
- features count
- rings count
- coordinates count
- response size by variant (`default/low`, `default/full`, `all/low`, `all/full`)

## 7. Risks and Mitigations

Risk: reduced default rank set hides niche geometries.
Mitigation: keep `rank_filter=all` mode for diagnostics.

Risk: simplification harms shape fidelity or hit testing.
Mitigation: tune tolerance by rank and validate click correctness on sampled locations.

Risk: stale cache responses after data refresh.
Mitigation: bounded TTL + restart invalidation; add manual clear hook if needed later.

## 8. Execution Order

1. Phase A
2. Phase B
3. Phase C
4. Phase D

Do not start later phases before Phase A acceptance is met and measured.
