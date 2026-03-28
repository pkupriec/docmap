# Phase 16 - Canonical Geo Identity And Deterministic Matching

This phase extends phase 15.

If phase 16 conflicts with prior geometry matching behavior, phase 16 governs identity and matching semantics.

## Objective

Implement a system-level fix for geometry and hierarchy matching:

- ID-first matching
- alias-second fallback
- strict canonical dictionaries
- deterministic conflict handling

Primary outcome:
eliminate name/alias ambiguity failures (for example Finland/Aland-style collisions) without presentation performance degradation.

## Production-Ready Reference Approach (Web-Verified)

Use the proven open-data pattern, adapted to DocMap architecture:

1. Canonical gazetteer IDs and hierarchy from Who's On First (WOF)
2. Concordance-based crosswalks to external IDs (`wof:concordances`) for deterministic identity linkage
3. Point-in-polygon/admin hierarchy resolution from Pelias spatial tooling (modern `pelias/spatial`; older chain used `pip-service`)
4. Alias matching only as controlled fallback when ID mapping is unavailable

References:

- WOF stable IDs and hierarchy model: https://whosonfirst.org/what/
- WOF concordances model: https://www.whosonfirst.org/docs/concordances/
- Pelias WOF importer (canonical source in Pelias stack): https://github.com/pelias/whosonfirst
- Pelias WOF admin lookup (admin hierarchy from WOF polygons): https://github.com/pelias/wof-admin-lookup
- Pelias spatial service (current PIP/hierarchy service): https://github.com/pelias/spatial

## Binding Inputs

Read and follow, in order:

1. `AGENT/INDEX.md`
2. `AGENT/PROJECT_CONSTITUTION.md`
3. `AGENT/EXECUTION_MODEL.md`
4. `AGENT/CURRENT_PHASE.md`
5. `ARCHITECTURE.summary.md`
6. `SERVICES.summary.md`
7. `PIPELINE.summary.md`
8. `DATA_MODEL.summary.md`
9. `PRESENTATION.summary.md`
10. `PRESENTATION_ARCHITECTURE.md`
11. `PRESENTATION_DATA_CONTRACT.md`
12. `PRESENTATION_API_SPEC.md`
13. `PRESENTATION_UX_SPEC.md`
14. `TASKS/phase13_map_geometry.md`
15. `TASKS/phase15_hierarchical_document_aggregation.md`
16. `database/schema.sql`
17. `infra/docker-compose.yml`

If conflicts appear, use that order.

## Non-Negotiable Constraints

- preserve architecture and service ownership
- keep presentation read-only
- do not add Redis/Kafka/Celery/NATS/new broker subsystems
- do not move extraction/geocoding/analytics logic into presentation runtime
- do not broaden fallback semantics beyond approved behavior
- prefer incremental, deterministic, test-backed changes

## Scope

### In Scope

- canonical identity model for geographic entities
- strict alias dictionary policy and conflict controls
- deterministic geocoder-to-canonical resolution
- deterministic analytics geometry matching by canonical IDs
- hierarchy consistency checks and guardrails
- regression tests and QA diagnostics for ambiguity failures

### Out Of Scope

- full geocoder replacement
- replacing frontend map stack
- uncontrolled UX redesign
- introducing new distributed runtime subsystems

## Canonical Data Model Changes

Add canonical geo tables owned by geocoder/analytics:

1. `geo_canonical_places`
- `canonical_id` (primary key, string; source-qualified, e.g. `wof:101736545`)
- `source` (`wof`)
- `source_id` (raw ID)
- `place_type` (`city`, `admin_region`, `country`, `continent`, `ocean`, `unknown`)
- `canonical_name`
- `parent_canonical_id` (nullable)
- `country_canonical_id` (nullable)
- `centroid_lat`, `centroid_lon` (nullable)
- `valid_from`, `valid_to` (nullable for supersession handling)

2. `geo_canonical_aliases`
- `canonical_id`
- `alias`
- `alias_type` (`exact_name`, `language_variant`, `historic_name`, `unsafe_parent_ref`)
- `normalized_alias`
- unique constraints scoped to safe alias classes

3. `geo_canonical_concordances`
- `canonical_id`
- `external_source` (`osm`, `geonames`, etc.)
- `external_id`
- unique (`external_source`, `external_id`)

4. Extend `geo_locations`
- `canonical_id` nullable at first, then backfilled
- `canonical_resolution_method` (`osm_identity`, `concordance`, `strict_alias`, `none`)
- `canonical_confidence` smallint or enum

Add indexes for:

- `geo_locations(canonical_id)`
- `geo_canonical_concordances(external_source, external_id)`
- `geo_canonical_aliases(normalized_alias, alias_type)`

## Strict Canonical Dictionary Policy

Alias classes:

- safe for primary matching: `exact_name`, `language_variant`
- never primary for country/admin_region: `unsafe_parent_ref` (for example sovereign references like "Finland" on Aland)

Rules:

- ID match always wins over aliases
- safe aliases are rank-scoped
- `unsafe_parent_ref` may only assist diagnostics, never primary entity selection
- ambiguous alias matches must be recorded and deterministically resolved or rejected with reason

## Service-Level Implementation Plan

### 1) Geocoder Layer

Files:

- `services/geocoder/nominatim_client.py`
- `services/geocoder/repository.py`
- `services/geocoder/service.py`

Tasks:

- keep collecting `osm_type`/`osm_id`
- add canonical resolution step:
  - resolve by (`osm_type`, `osm_id`) via concordances
  - fallback to strict alias+rank dictionary only when no ID mapping exists
- persist `canonical_id` and resolution metadata on `geo_locations`
- emit structured logs for ambiguous and unresolved canonical mappings

### 2) Analytics Layer

Files:

- `services/analytics/scripts/build_admin_boundaries_source.py`
- `services/analytics/geometry_assets.py`
- `services/analytics/service.py`

Tasks:

- rebuild boundary source generation from canonical dictionary rules
- remove over-broad alias ingestion for country/admin matching
- match `bi_locations` to geometry by canonical ID first
- use alias fallback only when canonical ID absent
- reject unsafe alias class for country/admin primary matching
- produce diagnostics:
  - `ambiguous_matches`
  - `unsafe_alias_hits`
  - `unmatched_by_rank`
  - coverage deltas vs previous build

### 3) Presentation Backend Layer

Files:

- `services/presentation/backend/repository.py`
- `services/presentation/backend/api.py`
- `services/presentation/backend/schemas.py`

Tasks:

- consume analytics outputs as identity-authoritative
- keep click aggregation semantics from phase 15
- preserve deterministic pagination/ordering
- expose optional diagnostics endpoint/metadata only if needed for operator visibility
- remove dependence on weak name fallback where canonical identity is available

### 4) Presentation Frontend Layer

Files:

- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/types.ts`

Tasks:

- keep current UX behavior unchanged
- prefer `location_id`/canonical-backed identity joins
- keep any name fallback purely defensive and non-authoritative
- avoid additional client-side matching complexity that can impact rendering performance

### 5) Runtime/Operations Layer

Files:

- `infra/docker-compose.yml`
- `docs/OPERATIONS.md`
- `docs/VERIFICATION.md`

Tasks:

- add optional offline tool path for canonical dictionary refresh:
  - WOF data import
  - concordance refresh
  - deterministic build report
- if Pelias spatial is used, keep it optional and bounded to build/reconciliation workflows, not required for presentation request path
- document repeatable refresh commands and failure handling

## Suggested Delivery Slices

1. schema + migrations + canonical tables
2. canonical import script and deterministic dictionary build
3. geocoder canonical resolution and persistence
4. analytics ID-first matching and diagnostics
5. presentation identity hardening (no UX change)
6. QA, backfill, and rollout checks

## Test Plan

### Unit Tests

- canonical resolver priority: ID > concordance > safe alias > none
- alias policy rejects unsafe parent references in primary country/admin matching
- deterministic tie-breaking on same-rank alias collisions

### Integration Tests

- geocoder response with valid OSM identity resolves to canonical ID
- analytics build produces boundary for previously failing case (Finland)
- hierarchy aggregation remains correct for city/admin/country/continent
- no regression in `/api/map/location/{id}/documents` pagination semantics

### Regression Fixtures (Required)

- Finland/Aland collision fixture
- Russia/Russian Federation naming fixture
- one continent-level high-cardinality fixture

### Performance Checks

- no increase in startup payload for presentation
- no additional map interaction latency due to identity changes
- analytics build time impact measured and documented

## Acceptance Criteria

- country/admin geometry matching is deterministic and ID-first
- alias-only ambiguity no longer drops valid high-level geometries silently
- canonical dictionary includes typed aliases and concordances
- diagnostics identify unresolved/ambiguous entities with actionable reasons
- existing presentation UX semantics remain unchanged
- automated tests cover canonical resolution and known collision regressions

## Definition Of Done

Done means:

- canonical ID model is implemented and populated
- geocoder and analytics use ID-first matching in production code paths
- known ambiguity class (Finland/Aland) is prevented by policy and tests
- phase 15 hierarchy click behavior remains intact
- docs and operations steps are updated for refresh/backfill/rebuild

