# Phase 14 - Presentation Visualization UX Iteration 2

This phase extends phase 13 presentation behavior.

If phase 14 conflicts with earlier visual defaults, phase 14 governs presentation visual and interaction clarity rules while preserving architecture and fallback constraints.

## Objective

Improve map readability, interaction clarity, and panel scanability in the presentation layer without redesigning architecture or replacing the frontend stack.

Primary outcomes:

- clearer map data-vs-basemap contrast
- explicit visual legend and state feedback
- stronger search-to-map feedback
- better document card information hierarchy
- improved link-visualization readability in dense states
- accessibility and error-message clarity improvements

## Binding Inputs

Read and follow, in order:

1. `docs/archive/legacy-agent/EXECUTION_SPEC.md`
2. `docs/archive/legacy-agent/PRESENTATION_EXECUTION_RULES.md`
3. `docs/architecture/ARCHITECTURE.md`
4. `docs/architecture/SERVICES.md`
5. `docs/architecture/DATA_MODEL.md`
6. `docs/architecture/PIPELINE.md`
7. `docs/presentation/PRESENTATION_ARCHITECTURE.md`
8. `PRESENTATION_DATA_CONTRACT.md`
9. `PRESENTATION_API_SPEC.md`
10. `PRESENTATION_UX_SPEC.md`
11. `PRESENTATION_IMPLEMENTATION_PLAN.md`
12. `docs/roadmap/phases/phase12_presentation_ux_iteration_1.md`
13. `docs/roadmap/phases/phase13_map_geometry.md`

If conflicts appear, use that order.

## Non-Negotiable Constraints

- preserve presentation as read-only service
- do not add writes from presentation runtime
- do not move geometry generation into presentation runtime
- do not extend hierarchy fallback beyond `city -> region/admin_region -> country`
- do not merge presentation with control-plane UI/runtime
- do not replace React/TypeScript/MapLibre/deck.gl/pdfjs-dist
- prefer incremental, local changes over broad rewrites

## Scope

### In Scope

- visual hierarchy and readability refinements in existing UI regions
- map styling and selection/readability tuning
- explicit legend and state indicators
- search results readability and map feedback polish
- document card visual hierarchy and metadata legibility improvements
- document link visualization decluttering controls
- accessibility and error-state messaging improvements
- tests and docs alignment for changed UX behavior

### Out of Scope

- new backend subsystems or brokers
- control-plane feature work
- mobile-first redesign
- new data model entities unrelated to presentation UX
- replacing map engine or frontend framework

## Detailed Work Items

### 1) Map Legibility and Visual Hierarchy

Implement:

- map style refinement so data overlays remain visually dominant
- reduced opacity/noise for non-selected geometry
- stronger selected-state styling (fill/stroke contrast and visibility on light/dark map areas)
- consistent color semantics for:
  - selected location
  - normal city point
  - polygon ranks
  - missing-boundary fallback points

Files likely touched:

- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/styles.css`

Acceptance checks:

- selected item remains visually obvious at all tested zoom levels
- missing-boundary fallback points remain distinguishable from city defaults

---

### 2) Legend and Status Clarity

Implement:

- compact in-map or panel-adjacent legend describing active visual encodings
- persistent active-mode indicator reflecting current priority state:
  - `Search`
  - `Pinned Location`
  - `Pinned Document`
  - `Hover`
  - `Idle`
- optional selected-entity summary chip showing name + linked document count

Files likely touched:

- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/styles.css`

Acceptance checks:

- users can identify symbol/color meaning without external docs
- active mode remains correct through modal/search/pin transitions

---

### 3) Search and Result Feedback Improvements

Implement:

- improved search result chip readability (rank cues, spacing, contrast)
- result summary text under search input (query and counts)
- short visual emphasis on newly focused search matches (non-blocking highlight pulse or equivalent)
- keep existing behavior:
  - `>=3` chars activation
  - deterministic ordering
  - map center/fit rules

Files likely touched:

- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/styles.css`

Acceptance checks:

- search-active panel remains search-driven
- map focus behavior remains contract-compliant for single/multi/document-only results

---

### 4) Document Card Scanability

Implement:

- stronger document card visual hierarchy:
  - title prominence
  - secondary metadata de-emphasis
  - consistent spacing rhythm
- compact metadata row (rank/mentions/offscreen, where available)
- offscreen linked-location count rendered as status badge rather than plain paragraph text
- preserve current interactions:
  - hover preview
  - pin toggle
  - thumbnail opens modal

Files likely touched:

- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/PdfThumbnail.tsx`
- `services/presentation/frontend/src/styles.css`

Acceptance checks:

- card content remains readable at default panel width
- pinned-card state remains visibly distinct

---

### 5) Document-Link Visualization Decluttering

Implement:

- improve line readability by encoding emphasis (opacity/width by relevance or viewport proximity)
- add low-risk declutter control (for example toggle for top-N visible links)
- add subtle transition for line appearance/disappearance to reduce visual flicker
- preserve deterministic behavior and existing recompute semantics

Files likely touched:

- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/styles.css`

Acceptance checks:

- dense link scenarios remain readable
- viewport drag updates remain responsive and stable

---

### 6) Accessibility and Error-State Messaging

Implement:

- improved contrast for low-visibility text/chips/buttons
- visible keyboard focus indicators for interactive elements
- contextualized error messages:
  - startup/load failure
  - search failure
  - location-doc fetch failure
- keep shared error-state model unless explicitly split by scope

Files likely touched:

- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/styles.css`

Optional backend touch:

- only if additional structured error detail is needed and still read-only

Acceptance checks:

- keyboard navigation remains usable for search, cards, modal close, and panel controls
- error messages provide actionable context without leaking internals

## API/Data Contract Impact Guidance

Phase 14 should avoid backend contract changes unless necessary for visual clarity features.

If payload additions are required (for example extra card metadata), then:

- update backend schemas/repository/API consistently
- update `PRESENTATION_DATA_CONTRACT.md` and `PRESENTATION_API_SPEC.md`
- update tests for deterministic ordering and dedupe guarantees

## Required Tests

Add or update automated tests for:

- active mode precedence rendering triggers
- search summary and panel-mode switching behavior
- legend rendering and symbol mapping presence
- offscreen badge behavior during viewport changes
- error-state messages by failure path (where feasible)

Maintain/update existing tests:

- `tests/test_presentation_api.py`
- any frontend test harness present in repository

Manual/E2E verification (required):

- startup load -> ready
- hover/pin/search transitions
- thumbnail modal open/close and pin persistence
- dense link scenario readability
- keyboard `Esc`, focus visibility, and clear/reset behavior

## Ordered Implementation Plan

1. baseline screenshot + behavior capture of current UI
2. implement map legibility/style token improvements
3. implement legend and active-mode indicator
4. implement search result readability and summary cues
5. implement document card hierarchy and offscreen badge
6. implement link declutter controls and visual transitions
7. implement accessibility/error-message polish
8. run automated tests
9. run browser-driven UX verification
10. update docs/spec files affected by behavior changes

## Required Outputs

- updated presentation frontend components/styles
- any minimal backend/support changes required by chosen UX features
- updated tests
- QA artifact update describing:
  - before/after behavior
  - verified scenarios
  - residual risks or deferred items

## Acceptance Criteria

- map overlays are visually clearer against basemap at default zoom range
- legend exists and matches actual marker/polygon semantics
- active interaction mode is visible and accurate
- search result context is clearer without changing deterministic behavior
- document card scanability is improved and pinned/offscreen states are clearer
- dense document-link visuals are more readable with decluttering option
- keyboard focus and contrast are improved for core controls
- no architecture boundary violations introduced
- fallback behavior remains `city -> region/admin_region -> country`

