# Phase 15 - Hierarchical Document Aggregation By Geometry Click

This phase extends phase 14.

If phase 15 conflicts with prior click-result behavior, phase 15 governs geometry-click document aggregation semantics.

## Objective

Implement deterministic hierarchy-based document retrieval for map clicks, without UI performance degradation.

Target behavior:

- click `city` -> show documents linked to that city only
- click `admin_region` -> show documents linked to that region and all descendant cities
- click `country` -> show documents linked to that country and all descendant admin regions and cities
- click `continent` -> show all documents from all hierarchy descendants under that continent

## Binding Inputs

Read and follow, in order:

1. `AGENT/EXECUTION_SPEC.md`
2. `AGENT/PRESENTATION_EXECUTION_RULES.md`
3. `ARCHITECTURE.md`
4. `SERVICES.md`
5. `PIPELINE.md`
6. `DATA_MODEL.md`
7. `PRESENTATION_ARCHITECTURE.md`
8. `PRESENTATION_DATA_CONTRACT.md`
9. `PRESENTATION_API_SPEC.md`
10. `PRESENTATION_UX_SPEC.md`
11. `TASKS/phase13_map_geometry.md`
12. `TASKS/phase14_presentation_visualization_iteration_2.md`

If conflicts appear, use that order.

## Non-Negotiable Constraints

- keep presentation service read-only
- do not introduce Redis/Kafka/Celery/NATS or new background subsystems
- do not move geometry generation to presentation runtime
- preserve existing stack (FastAPI + React/TS + MapLibre/deck.gl)
- prefer targeted changes over architecture rewrites
- keep deterministic ordering for document results
- avoid UI stalls when selecting high-cardinality geometries (country/continent)

## Scope

### In Scope

- hierarchy-complete location lineage needed for click aggregation
- backend query semantics for descendant aggregation by rank
- API pagination and response metadata for large result sets
- frontend incremental rendering and list virtualization/loading strategy
- regression tests for hierarchy semantics and perf safeguards

### Out of Scope

- new map engine/framework
- new control-plane features
- unrelated UX redesign
- authoring/editing geometry from presentation

## Required Behavior Contract

For `/api/map/location/{location_id}/documents`:

- `city`: scope is exact location only
- `admin_region`: scope is subtree (`admin_region` + descendants)
- `country`: scope is subtree (`country` + descendants)
- `continent`: scope is subtree (`continent` + descendants)
- `ocean`: keep current behavior unless separately specified; do not broaden implicitly

Alias safety:

- if clicked location is an alias-duplicate node with zero docs, resolver may remap to canonical peer (same semantic country/region key) before scope expansion

## Service-Level Change Plan

### 1) Database and Analytics Layer

#### 1.1 Hierarchy completeness

Update analytics lineage build so `bi_location_hierarchy` supports continent rollups:

- ensure country -> continent parent linkage exists where data is available
- keep existing city -> admin_region -> country lineage
- keep acyclic guarantees

Potential touchpoints:

- `services/analytics/service.py` (`build_bi_locations`, `build_bi_location_hierarchy`)
- `services/analytics/geometry_assets.py` (canonical target dedupe remains in place)

#### 1.2 Canonical duplicate handling

Harden duplicate alias handling used by boundaries and click resolution:

- select canonical node by stable priority:
  - has OSM identity
  - higher document_count
  - stable ID tiebreak
- emit collision diagnostics in build logs and coverage output

#### 1.3 Query/index support

Ensure query paths remain fast for descendant expansion:

- verify/create indexes for:
  - `bi_location_hierarchy(ancestor_location_id, descendant_location_id, depth)`
  - `bi_document_locations(location_id, document_id)`
  - `bi_locations(location_id, location_rank, document_count)`

### 2) Presentation Backend

#### 2.1 Replace ancestor-fallback semantics with rank-aware scope expansion

Refactor document resolution logic:

- resolve canonical clicked node first (alias-safe)
- determine scope strategy by `location_rank`
- compute scoped location set from `bi_location_hierarchy` descendants for aggregating ranks
- aggregate unique documents across scope

Likely files:

- `services/presentation/backend/repository.py`
- `services/presentation/backend/api.py`
- `services/presentation/backend/schemas.py`

#### 2.2 Pagination and metadata

Add API controls to prevent oversized payloads for continent/country:

- query params: `limit`, `offset`
- response metadata:
  - `total_items`
  - `returned_items`
  - `scope_location_count`
  - `scope_rank`
  - `resolved_location_id`

Default limits must be conservative and deterministic.

#### 2.3 Deterministic ordering

Maintain stable order for aggregated documents:

- canonical number, then URL, then document_id (or equivalent documented stable ordering)

### 3) Presentation Frontend

#### 3.1 Click behavior alignment

Adjust selection flow to consume paginated hierarchical responses:

- preserve current click/hover/pin model
- for large scopes, show first page immediately and load more on demand

Likely files:

- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/api.ts`
- `services/presentation/frontend/src/types.ts`

#### 3.2 Performance-safe rendering

Implement UI safeguards:

- incremental append for additional pages
- list virtualization or equivalent for long document lists
- loading indicators for page fetches
- avoid map re-render storms while scrolling list

#### 3.3 UX clarity

Show scope context in panel header:

- example: `Country scope: 1,284 docs from 143 locations`

## Testing Plan

### Backend tests

Add/expand tests for:

- city exact-scope behavior
- admin_region descendant aggregation
- country descendant aggregation
- continent descendant aggregation
- alias-node canonical remap behavior
- pagination determinism (`limit/offset` stability)

Likely files:

- `tests/test_presentation_repository.py`
- `tests/test_presentation_api.py`
- `tests/test_analytics_service.py`
- `tests/test_analytics_geometry_assets.py`

### Frontend tests

Add/update tests for:

- click -> first page render
- load-more behavior and dedupe safety
- scope summary display correctness
- no blocking UI on large mocked result sets

### Manual/E2E checks (required)

- click city with known direct docs
- click admin_region with mixed region+city docs
- click country with high cardinality
- click continent with very high cardinality
- verify panel responsiveness during map pan/zoom + list scroll

## Performance Acceptance Criteria

- initial click response payload bounded by default `limit`
- first results visible quickly (no full-scope wait required)
- map interaction remains smooth while list is populated
- no frontend freeze on continent selections
- backend query plan uses indexed hierarchy/document paths

## Ordered Execution Plan

1. define/lock API contract additions (`limit`, `offset`, summary metadata)
2. implement analytics lineage completeness for continent rollups
3. implement backend scoped aggregation query path by rank
4. add backend pagination + deterministic ordering
5. update frontend client/types and panel pagination UX
6. add/expand automated tests (backend then frontend)
7. run manual high-cardinality click validation
8. document residual edge cases and thresholds

## Definition of Done

Done means:

- click behavior matches required rank semantics exactly
- alias duplicates do not cause empty false negatives
- large-scope selections are paginated and responsive
- tests cover rank scope rules and pagination determinism
- no measurable UI performance regression in high-cardinality scenarios
