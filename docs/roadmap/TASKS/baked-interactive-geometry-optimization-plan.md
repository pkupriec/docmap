# Baked Interactive Geometry Optimization Plan

Date: 2026-04-17
Owner: Presentation runtime team
Status: Approved for implementation

## 1. Objective

Replace runtime-served viewport boundary GeoJSON as the normal presentation path with an analytics-baked, interactive, low-overhead base geometry layer that keeps the UI smooth and materially reduces end-user machine load.

Primary product goals:
- fastest possible visible UI responsiveness for end users
- long-term architecture that removes heavy geometry work from the browser/request hot path
- no requirement to preserve backward compatibility unless later instructed

Target outcomes:
- first useful map interaction remains responsive while geometry continues loading in background
- normal map viewing uses baked artifacts, not live `/api/map/boundaries` viewport responses
- selected/highlighted geometry remains available through small live API reads only
- end-user CPU and memory cost during pan/zoom/hover/click is reduced by at least 5x versus current baseline
- stretch target: 20x improvement in measured UI responsiveness and/or main-thread load on representative local scenarios

## 2. User Decisions Captured

These requirements are explicit and must govern implementation:

- simplification modes exposed to the user:
  - `Full precise`
  - `Balanced precise`
  - `Simplified`
  - `Primitive`
- `Full precise` means no simplification
- simplification control is required in the UI control plane for the current user session
- default precision must also be configurable outside the session override path
- normal viewing must use baked geometry; live API remains only for selected/highlighted geometry
- background loading should eventually fetch all geometry for the chosen simplification mode
- baked geometry must remain interactive for hover + click select
- artifact generation belongs to analytics-owned preparation, not presentation runtime writes
- artifact format may be decided iteratively based on measured efficiency
- no backward-compatibility fallback path is required for the old normal-viewing boundary delivery model
- simplification control is by zoom band only, not by rank

## 3. Validated Current State (Code-Backed)

Validated from implementation on 2026-04-17:
- presentation runtime is FastAPI + React/Vite with MapLibre and deck.gl
- normal boundary viewing still depends on `GET /api/map/boundaries`
- boundary responses are assembled from `bi_admin_boundaries`
- repository path still reads `feature_json` rows and parses JSON at request time
- frontend still maintains substantial polygon state client-side and rebuilds map layers during interaction-sensitive flows
- baked static boundary artifacts do not yet exist as the primary presentation path

Current heavy paths:
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`
- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/analytics/*` (new artifact-generation ownership will be added here)

## 4. Scope

In scope:
- analytics-owned generation of baked presentation geometry artifacts
- artifact format decision through measured iteration
- presentation frontend cutover to baked interactive geometry as the normal base layer
- live API retention only for selected/highlighted geometry fetches
- session-level precision control in UI
- configurable default precision
- background loading strategy for the chosen mode
- documentation, verification, and UI/perf test updates

Out of scope:
- control plane semantics unrelated to precision selection
- geocoder behavior changes
- backward-compatible preservation of the current viewport boundary API as the normal rendering path
- presentation-runtime writes

## 5. Architecture Direction

Canonical target architecture:
1. Analytics stage produces baked presentation geometry artifacts from analytics-owned data.
2. Presentation frontend renders baked artifacts directly as the normal boundary/base layer.
3. Baked layer remains interactive using minimal stable feature properties:
   - `location_id`
   - `location_rank`
   - `location_name`
4. Live presentation API is retained only for small explicit geometry fetches tied to:
   - selected location
   - highlighted search results
5. Presentation no longer depends on runtime assembly of broad viewport GeoJSON for ordinary viewing.

Important constraint:
- the project constitution fixes pipeline order as `crawl -> extract -> geocode -> analytics -> export`
- therefore baked geometry generation must be implemented as an analytics-owned deliverable within analytics behavior, not as a new top-level pipeline stage

## 6. Precision Model

Required precision modes:
- `Full precise`
- `Balanced precise`
- `Simplified`
- `Primitive`

Required semantics:
- `Full precise`: canonical unsimplified geometry
- all other modes: deterministic simplification baked ahead of runtime
- simplification is controlled by zoom band only
- no per-rank tuning in this phase

Required control surfaces:
1. UI session control
   - user can switch precision mode for the current session in the control-plane UI
2. Configurable default
   - a default precision mode must be configurable for presentation startup/runtime

Recommended config shape:
- one named mode active at runtime
- one tolerance table per mode keyed by zoom band
- no user-facing numeric tuning in this phase

## 7. Artifact Strategy and Iteration Rule

Phase A decision (2026-04-17):
- canonical baked artifact format: **standard vector tile directory (`z/x/y`)**
- measured comparison record: `docs/qa/baked_interactive_geometry_phase_a_report_2026-04-17.md`

Candidate implementations:
1. `pmtiles` vector tiles
2. standard vector tile directory (`z/x/y`)
3. only if the above prove materially worse than expected, another tile-like baked format with equivalent interaction support

Iteration rule:
- start with a short measured comparison between `pmtiles` and standard vector tiles
- choose the format that yields the best balance of:
  - fastest startup/interaction
  - lowest end-user CPU/memory load
  - simplest operational delivery
  - cleanest interactivity in MapLibre
- once chosen, that format becomes canonical for the remainder of this phase

Canonicalization rule after Phase A:
- keep `z/x/y` as the format for Phase B+ implementation unless a later measured regression report explicitly reopens the decision.

## 8. Background Loading Policy

Required behavior:
- viewport-needed geometry for the chosen mode loads first
- after the initial interactive state is ready, the app progressively background-loads the rest of the baked geometry for that same chosen mode
- background loading must never block or materially degrade interaction responsiveness

Guardrails:
- background work should be throttled and cancellable
- visible viewport and active interaction always take priority over preload
- preload strategy must be measured against machine-load impact
- start with low preload concurrency (1-2 in-flight tile requests) and only widen when measured interaction metrics remain stable
- background preload must pause/cancel on user viewport movement and resume only after interaction settles
- no preload rule may reintroduce broad live `/api/map/boundaries` normal-view dependency

## 9. Implementation Phases

### Phase A - Baseline, Candidate Benchmark, and Contract Cutover Design

Purpose: establish the measured baseline, compare artifact strategies, and define the new canonical contract before broad implementation.

Tasks:
1. Measure current baseline using representative UI scenarios:
   - initial load
   - low-zoom pan
   - regional pan
   - hover/click select
   - search highlight
2. Record:
   - startup timing
   - first useful interaction timing
   - main-thread activity
   - request counts
   - payload sizes
   - browser memory/CPU indicators where available
3. Prototype and compare at least:
   - `pmtiles`
   - vector tile directory
4. Decide canonical baked artifact format using measured results.
5. Design the post-cutover contract:
   - baked geometry for normal viewing
   - live API only for selected/highlighted geometry
   - no normal-view fallback to current viewport GeoJSON path

Acceptance:
- measured baseline is documented
- artifact format decision is documented and justified
- the cutover contract is explicit and docs-aligned

Phase A status (2026-04-17): complete  
Execution record: `docs/qa/baked_interactive_geometry_phase_a_report_2026-04-17.md`

### Phase B - Analytics-Owned Baked Geometry Generation

Purpose: move geometry preparation out of runtime and into analytics-owned deterministic artifact generation.

Tasks:
1. Add analytics-owned geometry bake outputs for all four modes:
   - `Full precise`
   - `Balanced precise`
   - `Simplified`
   - `Primitive`
2. Bake zoom-band-specific geometry detail for each mode.
3. Ensure generated features include only the metadata needed for baked interactivity.
4. Version artifact outputs deterministically.
5. Keep generation reproducible for clean-start and existing-db workflows.
6. Update docs to make these artifacts canonical presentation inputs.

Acceptance:
- analytics generation produces deterministic baked artifacts for all modes
- `Full precise` contains unsimplified geometry
- artifact metadata is sufficient for hover + click selection in the baked layer

Phase B status (2026-04-19): complete  
Implementation anchor points:
- `services/analytics/baked_geometry_assets.py`
- `services/analytics/service.py` (`presentation_baked_geometry` step)
- `services/analytics/scripts/rebuild_admin_boundaries.py`

### Phase C - Presentation Cutover to Baked Interactive Base Layer

Purpose: make baked geometry the canonical normal-view rendering path.

Tasks:
1. Render the baked base layer directly in MapLibre.
2. Keep the baked layer interactive for:
   - hover
   - click select
3. Remove the old live viewport-boundary path from normal viewing.
4. Retain live API only for selected/highlighted geometry fetches.
5. Minimize React/deck.gl participation in broad polygon rendering.
6. Keep points and other dynamic overlays working with the new geometry source.

Acceptance:
- normal viewing no longer depends on live broad boundary GeoJSON
- baked layer interactivity works for hover + click select
- selected/highlighted live overlays merge cleanly with the baked layer

Phase C status (2026-04-20): complete  
Implementation anchor points:
- `services/presentation/frontend/src/MapView.tsx` (baked vector tile base + hover/click)
- `services/presentation/frontend/src/App.tsx` (normal-view baked source, explicit live overlays only)
- `services/presentation/backend/api.py` (`/api/map/baked/manifest`, `/api/map/baked/tiles/...`)
- `tests/test_presentation_browser_regression.py`

### Phase D - Precision Control Surfaces

Purpose: give the user explicit control over simplification without reintroducing heavy runtime processing.

Tasks:
1. Add current-session precision mode control to the control-plane UI.
2. Add configurable default precision for presentation startup/runtime.
3. Ensure mode changes switch the baked geometry source cleanly for the session.
4. Define and document UX behavior for mode switching:
   - loading indicator
   - state persistence for current session
   - interaction continuity where possible

Acceptance:
- user can switch precision modes for the current session
- default precision is configurable
- switching modes does not break interactivity or selection semantics

Phase D status (2026-04-20): complete  
Implementation anchor points:
- `services/presentation/frontend/src/App.tsx` (session precision selector + mode switch wiring)
- `services/presentation/backend/api.py` (`DOCMAP_PRESENTATION_DEFAULT_PRECISION_MODE` default-mode resolution)
- `tests/test_presentation_api.py`
- `tests/test_presentation_browser_regression.py`

### Phase E - Background Full-Mode Loading

Purpose: satisfy the requirement that all data for the chosen mode eventually becomes available without blocking interaction.

Tasks:
1. Implement progressive background loading for the chosen mode after initial readiness.
2. Prioritize viewport-relevant geometry first, then preload remaining geometry for that mode.
3. Throttle preload to keep machine load low.
4. Add instrumentation to verify preload does not materially regress responsiveness.

Acceptance:
- chosen-mode geometry progressively becomes available in background
- interaction remains smooth while preload is active
- preload policy is measurable and bounded

Phase E status (2026-04-20): complete  
Implementation anchor points:
- `services/presentation/frontend/src/App.tsx` (throttled background preload + pause/resume on viewport interaction)
- `services/presentation/backend/api.py` (`/api/map/baked/tile-index`)
- `tests/test_presentation_api.py`
- `tests/test_presentation_browser_regression.py`

### Phase F - Iterative Performance Validation and Removal of Legacy Normal Path

Purpose: validate the speedup claims and make the baked path canonical in docs/tests.

Tasks:
1. Add repeatable UI/performance tests for representative scenarios.
2. Measure before/after against the Phase A baseline.
3. Iterate until:
   - minimum 5x improvement is demonstrated, or
   - 20x target is reached, or
   - a documented blocker explains why further improvement is not currently justified
4. Update canonical docs to remove the old normal-view boundary-delivery model.
5. Remove obsolete code/doc/test paths that imply backward compatibility the user did not require.

Acceptance:
- minimum 5x improvement is demonstrated on agreed representative scenarios
- 20x remains the explicit stretch target
- docs describe the baked path as canonical

## 10. Deliverables

Required code deliverables:
- analytics-owned geometry baking pipeline
- chosen baked artifact delivery path
- MapLibre baked interactive base layer
- live explicit overlay geometry path for selection/highlight only
- control-plane session precision selector
- configurable default precision
- background preload mechanism for the chosen mode
- UI/perf validation coverage

Required docs updates:
- `docs/presentation/PRESENTATION_ARCHITECTURE.md`
- `docs/presentation/PRESENTATION_DATA_CONTRACT.md`
- `docs/presentation/PRESENTATION_API_SPEC.md`
- `docs/presentation/PRESENTATION_UX_SPEC.md`
- `docs/operations/VERIFICATION.md`
- relevant QA and task docs

## 11. Verification Protocol

Required representative scenarios:
1. Cold load with default precision
2. Cold load with `Full precise`
3. Low-zoom world navigation
4. Regional pan/zoom
5. Hover on baked polygon
6. Click select on baked polygon
7. Search-highlight live overlay on top of baked base layer
8. Session precision switch
9. Background preload while interacting

Required measurements:
- first useful interaction
- pan/zoom responsiveness
- hover/click responsiveness
- request counts and payload bytes
- browser CPU/main-thread activity
- browser memory pressure indicators where available
- artifact size by mode
- preload impact while interacting

Phase F validation preflight gates (sharpened 2026-04-20):
- `GET /api/map/baked/manifest` must succeed before recording "after" metrics.
- initial load traffic for normal view must include baked manifest/tiles and must not include `/api/map/boundaries`.
- if baked artifacts are missing, run analytics-owned artifact generation first and restart presentation before benchmarking.
- Phase F measurement runs that do not satisfy these gates are invalid and must not be used for threshold claims.

Success thresholds:
- minimum acceptable improvement: 5x versus current baseline
- target improvement: 20x versus current baseline

## 12. Risks and Mitigations

Risk: background loading of all geometry still increases end-user load too much.
Mitigation: throttle aggressively, prioritize visible work, and validate preload with measurements before widening it.

Risk: baked interactivity lacks enough metadata for clean hover/click behavior.
Mitigation: include stable minimal identity/display properties in baked features and fetch richer detail on demand only when needed.

Risk: `Full precise` mode remains expensive.
Mitigation: keep it available as requested, but measure and document its cost explicitly; do not let it define the default path if it harms responsiveness.

Risk: artifact format choice is made too early.
Mitigation: require a measured Phase A comparison before canonizing the format.

Risk: analytics bake outputs drift from presentation expectations.
Mitigation: document artifact contract explicitly and verify it in automated tests.

## 13. Execution Order

1. Phase A
2. Phase B
3. Phase C
4. Phase D
5. Phase E
6. Phase F

Rules:
- do not implement the full cutover before the artifact-format comparison is recorded
- do not preserve the old normal-view live boundary path unless later instructed
- keep analytics ownership explicit and presentation runtime read-only
