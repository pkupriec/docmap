# Architectural Anti-Patterns

Avoid these patterns to preserve deterministic behavior and service boundaries.

## 1. Merging Service Responsibilities

Do not fold crawler, extractor, geocoder, analytics, control, and presentation concerns into one module.

## 2. Bypassing Snapshot Inputs

Extractor must operate on `document_snapshots.clean_text`, not raw crawler HTML.

## 3. Mixing Extraction and Geocoding

Extractor writes mentions. Geocoder resolves and links locations.

## 4. Writing Outside Service-Owned Tables

- crawler: `scp_objects`, `documents`, `document_snapshots`
- extractor: `extraction_runs`, `location_mentions`
- geocoder: `geo_locations`, `document_locations`
- analytics: `bi_*`
- control: `pipeline_*`
- presentation: read-only

## 5. Querying Operational Tables for Presentation Analytics

Presentation must use BI projections, not operational source tables.

## 6. Storing Derived Data in Source Fact Tables

Do not put analytics-only fields into operational tables.

## 7. Mutating Historical Snapshots

Do not rewrite existing snapshot payloads; create a new snapshot when content changes.

## 8. Forcing Full Recrawl Without Need

Respect incremental and scoped run modes.

## 9. Silent Contract Changes

Do not change extraction JSON or API payload contracts without synchronized docs/tests.

## 10. Hardcoded Runtime Values

Use environment variables and compose settings, not machine-local constants.

## 11. Monolithic Files as Cross-Service Dumps

Keep modules focused and bounded by service ownership.

## 12. Failing Entire Runs for Single-Item Errors

Prefer item-level failure isolation with progress/log visibility.

## 13. Breaking Idempotency

Reruns, retries, and resumes must not duplicate or corrupt state.

## 14. Silent Architectural Redesign

When architecture must change, document it explicitly and align code + docs in one change set.

## Final Rule

When uncertain, consult in this order:
1. `docs/index.md`
2. `docs/architecture/SERVICES.md`
3. `docs/architecture/ARCHITECTURE.md`
4. `docs/architecture/PIPELINE.md`