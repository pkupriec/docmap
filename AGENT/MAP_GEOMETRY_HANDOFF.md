# Map Geometry Handoff

Purpose: preserve the agreed implementation context for the next session after context compaction.

## User Goal

Replace most point markers in the presentation map with real geometry while preserving the current UX behavior in full.

Target rendering model:

- city -> point
- admin region -> polygon using real region boundary
- country -> polygon using real country boundary
- continent -> polygon using continent shape
- ocean -> polygon using ocean shape

## Explicit User Decision

Do NOT extend hierarchy fallback beyond the current model.

Keep hierarchy fallback exactly:

- city -> region -> country

Do not add continent/ocean fallback in backend or frontend panel logic.

## Current Repository State

Presentation stack:

- React
- TypeScript
- MapLibre GL JS
- deck.gl
- pdfjs-dist

Relevant files:

- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`
- `services/analytics/geometry_assets.py`
- `services/analytics/service.py`
- `services/geocoder/nominatim_client.py`
- `services/geocoder/repository.py`
- `database/schema.sql`

Current geometry behavior:

- frontend loads static `admin_boundaries.geojson`
- polygons are matched by lowercased location name in `MapView.tsx`
- city remains point
- region/country may render as polygon
- polygon-to-point fallback exists at low zoom

Current problems discovered during analysis:

1. `admin_boundaries.coverage.json` shows almost no real coverage:
   - countries: 190
   - regions: 829
   - matched_countries: 1
   - matched_regions: 1
2. `services/analytics/assets/admin_boundaries_source.geojson` is effectively a stub/demo dataset, not a production boundary source.
3. Polygon matching is currently string-based by `location_name`, which is fragile and insufficient.
4. Upstream location model does not distinguish `continent` or `ocean`.
5. Current geocoder precision model is effectively limited to:
   - `city`
   - `admin_region`
   - `country`
   - `coordinates`
   - `unknown`

## Key Architectural Conclusion

This task is not a frontend-only change.

To achieve reliable polygon rendering, the implementation must change the data flow across:

- geocoder metadata persistence
- analytics geometry asset generation
- presentation API/frontend contracts

The frontend renderer alone is not the real blocker.
The real blocker is stable geometry identity and high-coverage source data.

## Recommended Direction

### 1. Separate rank from precision

Do not overload `precision` with semantic type.

Recommended new concept:

- `location_rank`: `city | admin_region | country | continent | ocean | unknown`

Keep `precision` as a confidence/granularity signal if needed.

### 2. Persist stable external geo identity from geocoder

Recommended new geocoder metadata to persist from Nominatim result when available:

- `osm_type`
- `osm_id`
- `category`
- `type`
- `place_rank`
- `boundingbox`

Reason:

- current string matching by normalized name is not reliable enough for geometry joins
- stable external ids are needed for robust asset generation and diagnostics

### 3. Keep geometry generation upstream and read-only for presentation

Preserve the current architecture rule:

- analytics owns geometry asset generation
- presentation consumes generated assets read-only
- presentation runtime must not generate or mutate geometry

### 4. Replace current stub boundary pipeline

`services/analytics/geometry_assets.py` should be redesigned to build a deterministic geometry asset keyed by `location_id`, not by `location_name`.

The generated asset should include polygons for:

- admin regions
- countries
- continents
- oceans

Cities remain points from BI coordinates.

### 5. Preferred external geometry sources

Primary recommendation:

- Natural Earth Admin 0 for countries
- Natural Earth Admin 1 for regions
- Natural Earth ocean polygons for oceans
- continent polygons derived from country geometries or sourced from Natural Earth regional layers

Optional fallback for unmatched admin regions:

- geoBoundaries, only for unresolved coverage gaps

Do not use runtime Nominatim polygon fetching as the primary rendering source.

### 6. Do not change hierarchy behavior

Preserve existing backend fallback semantics:

- city -> region -> country

Continent/ocean are rendering classes only for now, not hierarchy fallback targets.

## Practical Implementation Sequence

### Iteration 1: data model and geocoder metadata

Expected areas:

- `database/schema.sql`
- geocoder repository/service/client
- analytics BI projection logic
- tests around geocoder normalization/classification

Goals:

- persist stable geo metadata
- introduce `location_rank`
- classify continent/ocean distinctly

### Iteration 2: analytics geometry asset rebuild

Expected areas:

- `services/analytics/geometry_assets.py`
- `services/analytics/service.py`
- geometry asset tests
- coverage diagnostics

Goals:

- build high-coverage geometry asset from real datasets
- key output by `location_id`
- report matched/unmatched counts by rank

### Iteration 3: presentation contract and renderer

Expected areas:

- `services/presentation/backend/schemas.py`
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`
- `services/presentation/frontend/src/types.ts`
- `services/presentation/frontend/src/api.ts`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/App.tsx`
- presentation API tests

Goals:

- expose `location_rank`
- consume geometry asset keyed by `location_id`
- render:
  - city as point
  - admin_region/country/continent/ocean as polygon
- preserve all existing hover/pin/search/PDF behavior

### Iteration 4: verification

Expected areas:

- presentation API tests
- analytics geometry tests
- geocoder tests
- Playwright/manual map verification

Verify:

- polygon click behavior matches point behavior
- pinned document behavior still works
- search/map sync still works
- no hierarchy fallback change was introduced

## Documentation Files Likely Needing Updates Next

The next session is expected to edit project markdown files to align the repository docs with the agreed direction.

Most likely update set:

- `README.md`
- `PROJECT.md`
- `ARCHITECTURE.md`
- `SERVICES.md`
- `PIPELINE.md`
- `DATA_MODEL.md`
- `PRESENTATION_ARCHITECTURE.md`
- `PRESENTATION_DATA_CONTRACT.md`
- `PRESENTATION_API_SPEC.md`
- `PRESENTATION_IMPLEMENTATION_PLAN.md`
- `PRESENTATION_UX_SPEC.md`
- `docs/DEVELOPMENT.md`
- `docs/OPERATIONS.md`
- `docs/VERIFICATION.md`
- `docs/REPOSITORY_MAP.md`
- `AGENT/PRESENTATION_EXECUTION_RULES.md`
- `TASKS/phase12_presentation_ux_iteration_1.md`
- `TASKS/phase12_code_alignment.md`
- `TASKS/phase12_execution_checklist`

## Special Documentation Rule Requested By User

In the next documentation-editing task, add an explicit repository instruction:

- GPT-5.4 is allowed to modify project markdown files
- other models may only execute instructions described in those markdown files and must not modify them unless explicitly allowed

This requirement has been requested by the user and must be reflected in the project markdown guidance during the next task.

## Installed Skills Relevant To This Work

Already available:

- `playwright`
- `playwright-interactive`
- `screenshot`
- `pdf`
- system `skill-installer`
- system `skill-creator`

No additional skill installation is currently required for the next step.
