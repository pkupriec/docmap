# Phase 13 - Real Geometry Map Rendering

This phase extends phase 12.

If phase 13 conflicts with the earlier mixed-geometry baseline, phase 13 governs map geometry implementation.

This file is intentionally written as a self-contained execution brief for `gpt-5.3-codex`.
Reading this file should provide enough context to start implementation autonomously, while still allowing the agent to verify details in the referenced repository files.

## Execution Prompt For GPT-5.3-Codex

You are implementing phase 13 of the DocMap presentation layer.

Your job is to preserve the current presentation behavior in full while replacing broad non-city point markers with real geometry.

You must work autonomously and execute the implementation end-to-end unless you hit a genuine blocker.

Your required stance:

- treat this markdown file as authoritative execution input
- do not rewrite project markdown files
- implement code, tests, and configuration required by this phase
- preserve architecture boundaries
- preserve all phase 12 interaction behavior
- keep presentation read-only
- do not extend hierarchy fallback beyond `city -> region -> country`

Before changing code:

1. read the files listed in `Authoritative Inputs`
2. inspect the current implementation files listed in `Current Code Map`
3. confirm the existing behavior in code, not just in docs
4. implement incrementally by layer
5. verify as much as possible

When finished:

1. report what changed
2. report what was verified
3. report remaining coverage gaps or open risks
4. do not modify markdown files unless the user explicitly overrides repository rules

## Markdown Authority

- `GPT-5.4` may modify project markdown files.
- `gpt-5.3-codex` and other non-`GPT-5.4` models must treat project markdown files as fixed execution instructions.
- non-`GPT-5.4` models should implement code, tests, and configuration required by this phase without rewriting the project markdown unless the user explicitly overrides that rule.

## Goal

Preserve the current presentation behavior in full while replacing broad non-city point markers with real geometry.

Target rendering model:

- city -> point
- admin region -> polygon
- country -> polygon
- continent -> polygon
- ocean -> polygon

## Explicit User Decision

Do NOT extend hierarchy fallback beyond the existing behavior.

Fallback remains exactly:

- city -> region -> country

`continent` and `ocean` are rendering ranks only in this phase.

They may be rendered on the map, but they must not become new document fallback targets in backend or frontend panel logic.

## Authoritative Inputs

Read these before implementation:

- `AGENT/EXECUTION_SPEC.md`
- `AGENT/PRESENTATION_EXECUTION_RULES.md`
- `AGENT/MAP_GEOMETRY_HANDOFF.md`
- `ARCHITECTURE.md`
- `SERVICES.md`
- `DATA_MODEL.md`
- `PIPELINE.md`
- `PRESENTATION_ARCHITECTURE.md`
- `PRESENTATION_DATA_CONTRACT.md`
- `PRESENTATION_API_SPEC.md`
- `PRESENTATION_IMPLEMENTATION_PLAN.md`
- `PRESENTATION_UX_SPEC.md`
- `TASKS/phase12_presentation_ux_iteration_1.md`
- `TASKS/phase12_code_alignment.md`
- `TASKS/phase12_execution_checklist`

If conflicts appear, use that order.

## Current Code Map

Current implementation is primarily in these files:

- `database/schema.sql`
- `services/geocoder/nominatim_client.py`
- `services/geocoder/repository.py`
- `services/geocoder/service.py`
- `services/analytics/service.py`
- `services/analytics/geometry_assets.py`
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`
- `services/presentation/backend/schemas.py`
- `services/presentation/frontend/src/types.ts`
- `services/presentation/frontend/src/api.ts`
- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/assets/admin_boundaries.geojson`
- `services/presentation/frontend/src/assets/admin_boundaries.coverage.json`
- `tests/test_geocoder_nominatim_client.py`
- `tests/test_analytics_geometry_assets.py`
- `tests/test_analytics_service.py`
- `tests/test_presentation_api.py`

## Current State Snapshot

### Presentation stack

- React
- TypeScript
- MapLibre GL JS
- deck.gl
- pdfjs-dist

### Current frontend geometry behavior

The current map implementation already has an early mixed-geometry path:

- `services/presentation/frontend/src/MapView.tsx` loads `admin_boundaries.geojson`
- polygons are matched by lowercased display name
- city stays point
- region and country may render as polygons
- polygon-to-point fallback exists at low zoom

### Current backend and data behavior

- presentation API is read-only over `bi_*`
- analytics owns geometry asset generation
- presentation must not generate geometry at runtime
- current hierarchy fallback is `city -> region -> country`

### Current geocoder behavior

Current upstream precision model is effectively limited to:

- `city`
- `admin_region`
- `country`
- `coordinates`
- `unknown`

There is no proper first-class `continent` or `ocean` rank in the current implementation.

## Known Problems Discovered During Analysis

These are not hypothetical; they were observed in the repository:

1. `services/presentation/frontend/src/assets/admin_boundaries.coverage.json` shows almost no useful coverage:
   - countries: 190
   - regions: 829
   - matched_countries: 1
   - matched_regions: 1
2. `services/analytics/assets/admin_boundaries_source.geojson` is effectively a stub or demo dataset, not a production boundary source.
3. Polygon matching is currently based on display-name string matching in the frontend and is not robust enough.
4. Upstream location model does not distinguish `continent` and `ocean`.
5. Current implementation cannot reliably attach real geometry to presentation locations at scale.

## Architectural Conclusions

This is not a frontend-only task.

To achieve reliable polygon rendering, implementation must touch:

- geocoder metadata persistence
- analytics geometry asset generation
- presentation API contracts
- frontend geometry matching and rendering

The main blocker is not `deck.gl` rendering.
The main blocker is stable geometry identity plus usable upstream geometry coverage.

## Required Outputs

- schema updates required for stable geo identity and `location_rank`
- geocoder metadata persistence needed for stable geometry matching
- analytics-owned geometry asset generator with real upstream data
- high-coverage geometry asset keyed by `location_id`
- coverage diagnostics by geometry rank
- presentation API and frontend contract updates for `location_rank`
- frontend rendering changes preserving all existing UX behavior
- test updates

## Scope

### Required

- preserve phase 12 search, hover, pin, PDF, and document-link behavior
- keep presentation read-only
- keep geometry generation in analytics-owned build logic
- keep city rendering as point
- render `admin_region`, `country`, `continent`, and `ocean` as polygon when geometry exists
- use stable identity for geometry matching
- add `location_rank`
- add verification for preserved fallback behavior

### Out Of Scope

- runtime geometry generation inside presentation
- geometry editing workflows
- freeform generated polygons
- extending fallback to `continent` or `ocean`
- merging presentation into control UI
- replacing React, TypeScript, MapLibre, or deck.gl

## Preferred Technical Direction

### 1. Separate rank from precision

Do not overload `precision` with semantic type.

Introduce or persist a separate `location_rank` concept:

- `city`
- `admin_region`
- `country`
- `continent`
- `ocean`
- `unknown`

Keep `precision` as a confidence or granularity signal if still useful.

### 2. Persist stable upstream geo metadata

Persist upstream geo metadata from Nominatim when available, such as:

- `osm_type`
- `osm_id`
- `category`
- `type`
- `place_rank`
- `boundingbox`

Why:

- display-name-only matching is not reliable enough
- stable upstream metadata is needed for better geometry matching and diagnostics

### 3. Keep geometry generation upstream

Preserve the current architecture:

- analytics generates geometry assets
- presentation consumes them read-only
- presentation runtime must not generate or mutate geometry

### 4. Replace the current stub boundary pipeline

`services/analytics/geometry_assets.py` should be redesigned around real source data and stable matching.

Target output expectations:

- deterministic asset
- keyed by `location_id`
- polygons for `admin_region`, `country`, `continent`, `ocean`
- cities remain point-only from BI coordinates

### 5. Preferred geometry sources

Preferred upstream datasets:

- Natural Earth Admin 0 for countries
- Natural Earth Admin 1 for admin regions
- Natural Earth ocean polygons for oceans
- continent polygons derived from suitable upstream world-region geometry

Optional fallback for stubborn admin-region gaps:

- geoBoundaries for unmatched cases only

Do not use runtime Nominatim polygon fetching as the main rendering source.

## Suggested Implementation By Layer

### Layer 1 - Schema and geocoder metadata

Likely files:

- `database/schema.sql`
- `services/geocoder/nominatim_client.py`
- `services/geocoder/repository.py`
- `services/geocoder/service.py`

Likely changes:

- add schema support for stable upstream geo metadata
- add schema support for `location_rank`
- classify continent and ocean distinctly
- keep existing geocoding/linking behavior stable

### Layer 2 - Analytics BI and geometry assets

Likely files:

- `services/analytics/service.py`
- `services/analytics/geometry_assets.py`

Likely changes:

- propagate `location_rank` into BI-facing data used by presentation
- redesign geometry asset generation around real source data
- emit assets keyed by `location_id`
- emit coverage diagnostics by rank

### Layer 3 - Presentation backend contract

Likely files:

- `services/presentation/backend/schemas.py`
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`

Likely changes:

- expose `location_rank` in location-oriented payloads
- preserve deterministic ordering
- preserve fallback semantics
- do not add fallback to continent or ocean

### Layer 4 - Presentation frontend renderer

Likely files:

- `services/presentation/frontend/src/types.ts`
- `services/presentation/frontend/src/api.ts`
- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`

Likely changes:

- use `location_rank`
- match polygons by stable identity instead of display name
- keep city as point
- render non-city supported ranks as polygons when geometry exists
- preserve hover, pin, search, modal, and line-visualization behavior

## Ordered Work Plan

1. inspect current implementation and confirm actual current behavior
2. update schema and persistence model for stable geo identity and `location_rank`
3. update geocoder normalization and classification logic for `continent` and `ocean`
4. update BI projection logic so presentation has the rank information it needs
5. redesign `services/analytics/geometry_assets.py` around real source data and identity-based matching
6. emit improved coverage diagnostics by rank
7. update presentation API schemas and response payloads for `location_rank`
8. update frontend types and map rendering to use identity-based geometry matching
9. preserve all current UX behavior, including pinned document and search interactions
10. add or update tests
11. run verification and report any remaining coverage gaps

## Acceptance Criteria

- city renders as point
- admin region renders as polygon when geometry exists
- country renders as polygon when geometry exists
- continent renders as polygon when geometry exists
- ocean renders as polygon when geometry exists
- polygon click behavior matches point click behavior
- hierarchy fallback remains `city -> region -> country`
- presentation remains read-only
- geometry assets are generated by analytics, not by presentation runtime
- geometry asset matching is not based solely on display-name string matching
- coverage diagnostics clearly show matched and unmatched targets by rank
- phase 12 interactions remain intact

## Minimum Tests

- geocoder classification tests for `location_rank`
- analytics geometry asset tests for identity-based output and coverage reporting
- presentation API tests for updated location payload shape
- map interaction verification for polygon click and hover behavior

## Suggested Verification Sequence

1. run targeted Python tests for geocoder, analytics, and presentation API
2. run any build or syntax checks needed by the touched files
3. if the local stack is available, verify presentation map behavior manually or via Playwright
4. confirm fallback behavior still resolves only through `city -> region -> country`
5. inspect generated coverage diagnostics and report remaining unmatched geometry

## Required Reporting At Completion

The implementing agent should explicitly report:

- what geometry source data was used
- which schema fields were added or changed
- how geometry is matched to `location_id`
- whether any rank still falls back to point due to missing geometry
- whether hierarchy fallback remained unchanged
- what tests or verification steps were actually run

## Final Reminder To GPT-5.3-Codex

Do the implementation, not a redesign.

Do not rewrite the markdown.
Do not add continent or ocean to fallback.
Do not move geometry generation into presentation runtime.
Do not preserve the current fragile display-name-only geometry matching if a stable identity path can be implemented.
