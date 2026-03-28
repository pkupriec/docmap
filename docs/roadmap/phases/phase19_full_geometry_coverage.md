# Phase 19 - Full Geometry Coverage For All Geocoded Locations

This phase extends phase 18.

If phase 19 conflicts with earlier partial-geometry behavior, phase 19 governs geocode and geometry coverage semantics.

## Objective

Implement deterministic end-to-end behavior so that:

1. all extractable location mentions are geocoded whenever possible;
2. all geocoded entities can load geometry when upstream geometry exists;
3. hierarchy supports recursive descendant behavior for larger-geometry hover/selection;
4. all available OSM admin hierarchy levels are supported (not limited to current subset);
5. rollout is direct cutover (no long-lived feature-flag split).

## Product Decisions (Locked)

The following decisions are binding for this phase:

- hierarchy depth target: all available OSM admin levels
- geometry source strategy: Natural Earth + OSM hybrid
- non-admin geographies to include when available: national parks and deserts
- boundary-intent handling when top geocode is point feature: store both point and boundary candidates, choose later in analytics
- reprocessing policy: full re-geocode + analytics rebuild for all mentions
- large-geometry interaction behavior: aggregate documents from selected geometry + all descendants recursively
- rollout mode: direct cutover
- startup payload guardrails: do not introduce new hard startup payload SLO in this phase

## Problem Statement

Current coverage and behavior are incomplete because:

- geocoder can return point-like features for boundary-intent mentions;
- geometry ingestion currently does not cover all admin levels;
- geometry matching/dedupe can drop legitimate targets;
- hierarchy behavior is not uniformly defined across deeper admin levels;
- existing source strategy is insufficient for parks/deserts and fine-grained administrative boundaries.

## Scope

### In Scope

- deterministic geocoding improvements for boundary-intent detection and candidate retention;
- canonical and identity matching support for deeper admin hierarchy;
- hybrid geometry ingestion pipeline (Natural Earth + OSM) with deterministic precedence rules;
- geometry support for national parks/deserts where upstream data is available and geocoded;
- analytics-side boundary selection from multiple geocode candidates;
- recursive hierarchy construction and descendant aggregation semantics;
- direct-cutover migration and full backfill procedure;
- tests, diagnostics, and documentation updates.

### Out Of Scope

- LLM-based geocoding or disambiguation decisions;
- manual geometry editing workflows;
- presentation UX redesign unrelated to hierarchy/coverage correctness.

## Architecture Constraints

- preserve pipeline direction: `crawl -> extract -> geocode -> analytics -> export`;
- presentation remains read-only (no runtime geometry authoring);
- matching/resolution stays deterministic and reproducible;
- full reprocess must be safe on populated databases.

## Deterministic Data Model Direction

### 1) Geocode candidate retention

When boundary-intent mention resolves to point-first Nominatim result:

- persist the top point candidate;
- also persist one or more boundary candidates (when found by deterministic follow-up query);
- defer final geometry target selection to analytics stage.

Implementation may use either:

- explicit candidate table(s), or
- structured candidate payload fields in geocoder-owned records.

Chosen shape must support deterministic replay and diagnostics.

### 2) Hierarchy model

- support all available OSM admin levels present in ingested data;
- preserve cross-rank parent/child graph with deterministic parent assignment;
- maintain recursive descendant closure used by large-geometry aggregation.

### 3) Hybrid geometry source rules

- Natural Earth remains baseline for global broad coverage;
- OSM-derived boundaries are added for finer admin levels and target classes (including parks/deserts when available);
- geometry matching order must be identity-first:
  1. `location_id` (exact)
  2. canonical ID
  3. OSM identity (`osm_type`, `osm_id`)
  4. deterministic alias fallback (last resort)

## Implementation Plan

### Slice 1 - Geocoder Candidate Model

Files:

- `services/geocoder/nominatim_client.py`
- `services/geocoder/repository.py`
- `services/geocoder/service.py`
- schema and migration files as needed

Tasks:

- add deterministic boundary-intent detection;
- query/store both point and boundary candidates where applicable;
- persist admin-level and type metadata required for downstream selection;
- keep deterministic tie-breaking.

### Slice 2 - Canonical/Identity Expansion

Files:

- `services/geocoder/scripts/*`
- canonical dictionary inputs/builders
- `services/geocoder/repository.py`

Tasks:

- expand canonical coverage beyond current limited admin subset;
- preserve OSM concordance-first resolution;
- ensure deeper admin levels and non-admin target classes can resolve to stable identity when data exists.

### Slice 3 - Hybrid Geometry Ingestion

Files:

- `services/analytics/scripts/*`
- `services/analytics/geometry_assets.py`
- `services/analytics/service.py`

Tasks:

- integrate Natural Earth + OSM geometry ingestion;
- include parks/deserts when mapped and geocoded;
- build deterministic merged geometry asset keyed by stable identity;
- emit per-rank/per-class coverage diagnostics.

### Slice 4 - Analytics Candidate Selection And Matching

Files:

- `services/analytics/geometry_assets.py`
- `services/analytics/service.py`

Tasks:

- choose final display/aggregation geometry from stored geocode candidates;
- remove lossy dedupe that collapses distinct entities;
- preserve canonical/identity-first matching;
- report dropped candidates and unresolved reasons.

### Slice 5 - Recursive Hierarchy Semantics

Files:

- `services/analytics/service.py`
- presentation read models/repository as needed

Tasks:

- maintain recursive descendant closure across expanded hierarchy;
- enforce selected-geometry + all-descendants aggregation semantics;
- keep deterministic behavior for repeated rebuilds.

### Slice 6 - Reprocess And Cutover

Files:

- control/orchestrator/pipeline wiring
- operations docs

Tasks:

- execute full re-geocode for all mentions;
- rebuild analytics artifacts from refreshed geocoder outputs;
- switch to direct cutover after verification (no long-running dual mode).

## Acceptance Criteria

1. Coverage
- all deterministically geocodable mentions are linked;
- geometry is loaded for all geocoded targets where upstream geometry exists;
- all available OSM admin levels encountered in data are supported.
- soft target: at least 95% coverage for items that are possible to resolve/load with the existing project toolset and configured upstream sources.

2. Correctness
- point+boundary dual-candidate behavior works deterministically for boundary-intent cases;
- hierarchy closure is recursive and stable;
- large-geometry hover/selection aggregates documents from selected geometry and all descendants recursively.

3. Reliability
- full re-geocode + analytics rebuild succeeds on populated DB;
- repeated runs produce reproducible assignments and geometry linkage.

4. Diagnostics
- unmatched targets are reported by rank/class/reason;
- dropped candidate decisions are logged with deterministic reason codes.

5. Rollout
- direct cutover is completed with no unresolved contract mismatch between geocoder, analytics, and presentation.

## Verification Plan

1. Automated tests
- geocoder dual-candidate and boundary-intent tests;
- identity-first geometry match tests across admin levels;
- recursive hierarchy and descendant aggregation tests;
- integration tests for parks/deserts where fixtures exist.

2. End-to-end runs
- clean bootstrap full pipeline run;
- populated DB full re-geocode + analytics rebuild;
- repeatability run to confirm deterministic outputs.

3. Diagnostics artifacts
- coverage by admin level and class;
- unmatched-by-reason report;
- candidate-selection decision report.

## Deliverables

- implementation across geocoder/analytics/presentation read paths as needed;
- schema/migration updates (if candidate persistence requires them);
- updated operations/verification docs;
- completion summary including:
  - hybrid geometry sources used,
  - identity and candidate-selection rules,
  - remaining unmatched classes,
  - cutover notes.

## Cutover Notes (Session Updates)

- startup migration path must include phase columns so existing DB volumes upgrade automatically without manual SQL
- geocode/full runs default to canonical refresh and missing-identity refresh
- UI exposes explicit from-scratch `full_refresh_geo_information` control; default remains off
- spatial hierarchy links are generalized to polygon intersections across countries and admin levels, not only specific classes
- geometry matching attempts are not restricted to a fixed class/tag subset when upstream geometry exists

## Coverage Interpretation

- the 95% target is a soft threshold, not a hard failure gate;
- "possible with existing project toolset" means resolvable/loadable using current pipeline capabilities, deterministic logic, configured data sources, and available upstream geometry at run time;
- diagnostics must explicitly separate:
  - impossible/missing-upstream-data cases
  - possible-but-currently-unmatched cases
