# Phase 18 - Deterministic Ambiguous Country Resolution

This phase extends phase 17.

If phase 18 conflicts with prior alias-only matching behavior, phase 18 governs ambiguous country/admin resolution semantics.

## Objective

Remove the root cause that makes country polygons disappear for ambiguous names (for example `Congo`) and solve the same class for analogous cases.

Primary outcomes:

- deterministic canonical resolution for ambiguous country/admin aliases
- no LLM/intellectual inference in geocoder for this phase
- reproducible behavior for both clean pipeline runs and full reprocessing of populated databases

## Problem Class

Current failure pattern:

1. mention text resolves to a valid geocoded record
2. canonical resolution falls back to alias matching
3. alias is ambiguous across multiple canonical places
4. canonical ID remains null
5. analytics dedupe/matching may retain an unresolved variant and lose polygon coverage

The fix target is the class of ambiguous aliases, not a Congo-only patch.

## Binding Inputs

Read and follow, in order:

1. `docs/agent/INDEX.md`
2. `docs/agent/PROJECT_CONSTITUTION.md`
3. `docs/agent/EXECUTION_MODEL.md`
4. `docs/roadmap/CURRENT_PHASE.md`
5. `ARCHITECTURE.summary.md`
6. `SERVICES.summary.md`
7. `PIPELINE.summary.md`
8. `DATA_MODEL.summary.md`
9. `docs/roadmap/phases/phase16_canonical_geo_identity_and_matching.md`
10. `docs/roadmap/phases/phase17_geocoder_owned_canonical_source_and_flow_direction.md`
11. `database/schema.sql`
12. `infra/docker-compose.yml`

If conflicts appear, use that order.

## Non-Negotiable Constraints

- keep pipeline direction `crawl -> extract -> geocode -> analytics -> export`
- keep extraction unchanged in this phase
- keep geocoder deterministic (no LLM decisions)
- preserve service ownership boundaries
- keep presentation read-only
- support both clean runs and deterministic reprocessing

## Scope

### In Scope

- deterministic disambiguation in geocoder for ambiguous country/admin aliases
- canonical concordance enrichment and resolver priority hardening
- analytics hardening so unresolved aliases do not drop valid polygons
- backfill/reprocessing path for already populated DBs
- tests and diagnostics for ambiguity classes (Congo and analogs)

### Out Of Scope

- extractor prompt redesign
- LLM-assisted geopolitical disambiguation
- frontend UX redesign

## Deterministic Resolution Model (No LLM)

Geocoder resolution order becomes:

1. `osm_identity` by (`osm_type`, `osm_id`) via `geo_canonical_concordances`
2. strict unique safe alias (`exact_name` / `language_variant`) in same `place_type`
3. deterministic ambiguity resolver (new) using only structured signals
4. unresolved with explicit reason when confidence threshold is not met

### Deterministic ambiguity resolver

For alias with multiple canonical candidates, compute per-candidate score from deterministic signals:

- exact OSM country/admin code agreement (if available from geocoder payload)
- candidate concordance hit on known external identifiers
- document-local supporting mentions already resolved to candidate hierarchy
- rank/parent consistency (`city -> admin -> country` or `admin -> country`)
- negative penalties for conflicting hierarchy signals

Resolver behavior:

- choose winner only when score gap and absolute score exceed configured thresholds
- otherwise keep unresolved as `ambiguous_alias`
- store diagnostic payload (`candidate_ids`, score breakdown, reason)

No natural-language reasoning, no model calls.

## Data Model / Persistence Changes

Minimal schema extensions (if missing) to support deterministic replayability:

1. extend `geo_locations` metadata:
- `canonical_resolution_method` values include `deterministic_ambiguity_resolver`
- `canonical_confidence` normalized score
- optional `canonical_resolution_details` JSONB for score breakdown and candidates

2. optional lightweight diagnostics table (if needed for audit at scale):
- `geo_resolution_events` keyed by mention/location with method, candidates, chosen ID, reason

All changes must remain compatible with full rebuild/backfill runs.

## Service-Level Implementation Plan

### 1) Geocoder

Files:

- `services/geocoder/repository.py`
- `services/geocoder/service.py`
- `services/geocoder/nominatim_client.py` (only if additional structured fields are required)
- canonical refresh scripts under `services/geocoder/scripts/*`

Tasks:

- implement deterministic ambiguity resolver after strict alias step
- enrich concordance ingestion where external IDs exist for country/admin entities
- persist resolver diagnostics and confidence
- add deterministic tie-breaking (stable ordering by canonical ID)
- add explicit reason codes:
  - `ambiguous_alias_insufficient_signal`
  - `ambiguous_alias_conflicting_signal`
  - `deterministic_disambiguated`

### 2) Analytics

Files:

- `services/analytics/geometry_assets.py`
- `services/analytics/service.py`

Tasks:

- harden country/admin dedupe to prefer canonical-resolved targets
- avoid dropping canonical-resolved target in favor of unresolved ambiguous alias
- preserve canonical-id-first boundary matching
- emit diagnostics for dropped unresolved duplicates and unresolved polygon targets

### 3) Control / Pipeline

Files:

- `services/control/orchestrator.py`
- `services/pipeline/service.py`
- UI mapping files only if new run options are exposed

Tasks:

- keep full reprocess mode for deterministic replay:
  - geocode all mentions
  - refresh missing identity enabled
  - analytics rebuild afterward
- ensure replay path is documented and callable from existing controls

## Reproducibility Plan

### Clean run

1. empty DB bootstrap
2. canonical refresh
3. full pipeline run
4. verify ambiguity fixtures produce stable canonical IDs and polygons

### Populated DB reprocessing

1. run full geocode reprocess over all mentions (with identity refresh)
2. rebuild analytics artifacts
3. compare before/after diagnostics:
  - unresolved ambiguous alias count
  - country/admin polygon coverage
  - hierarchy integrity checks

Runs must be deterministic across repeated executions on same input.

## Ordered Delivery Slices

1. resolver contract + reason codes + tests (unit)
2. geocoder deterministic ambiguity resolver implementation
3. concordance enrichment path and refresh integration
4. analytics dedupe hardening for canonical-preferred behavior
5. replay/backfill command path verification
6. docs + operational verification checklist

## Test Plan

### Unit tests

- resolver priority order (osm identity > strict alias > deterministic resolver > unresolved)
- deterministic tie-breaking with stable output
- confidence threshold behavior
- no false positive canonical assignment on low-signal ambiguity

### Integration tests

- Congo/DRC fixture: both countries resolvable when structured signals exist
- analogous fixture set (`Korea`, `Guinea`, etc.) with deterministic outcomes
- analytics boundary build does not lose polygon when canonical-resolved target exists

### Replay tests

- same dataset, repeated full reprocess -> identical canonical assignments
- populated DB backfill reduces unresolved ambiguity and increases stable polygon coverage

## Acceptance Criteria

- ambiguous country/admin aliases are handled by deterministic algorithmic logic
- no LLM-based decisions are introduced in geocoder
- extractor remains unchanged
- Congo-class failures no longer cause polygon loss when sufficient structured signals exist
- insufficient-signal cases stay explicitly unresolved with diagnostics (no silent wrong match)
- clean run and populated DB reprocess produce reproducible outputs

## Definition Of Done

Done means:

- phase 18 implementation is merged with tests
- deterministic ambiguity resolver is active in geocoder
- analytics no longer drops valid polygon coverage due to unresolved alias winner selection
- replay/backfill procedure is documented and verified
- diagnostics provide actionable reasons for remaining unresolved ambiguous aliases

