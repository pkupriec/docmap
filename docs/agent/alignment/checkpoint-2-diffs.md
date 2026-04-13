# Checkpoint 2 Diffs (Presentation Backend)

Date: 2026-03-28

## Resolved in this checkpoint

1. `docs/presentation/PRESENTATION_API_SPEC.md` had overly broad not-found wording.
- Code truth: `/api/map/document/{id}` and `/api/map/document/{id}/pdf` return `404 {"error":"not_found"}`, while `/api/map/location/{id}/documents` returns `200` with empty payload when unresolved.

2. `docs/presentation/PRESENTATION_API_SPEC.md` did not explicitly state API validation vs repository short-query behavior.
- Code truth: API accepts `q` length `>=1`; repository returns empty arrays for trimmed queries `<3`.

3. `docs/presentation/PRESENTATION_ARCHITECTURE.md` listed fixed non-city rank ladders.
- Code truth: only city rank is explicitly filtered to city; non-city scopes use hierarchy descendants without additional rank constraints.

4. `docs/presentation/PRESENTATION_DATA_CONTRACT.md` implied geometry-driven aggregation semantics.
- Code truth: location-documents aggregation is hierarchy-driven in backend repository logic.

5. `docs/presentation/PRESENTATION_DATA_CONTRACT.md` did not explicitly state unresolved-location response semantics.
- Code truth: unresolved location returns `resolved_location_id=null` and empty `items` with HTTP 200.

## Deferred (out of checkpoint scope)

- Frontend interaction/state-model fidelity (`services/presentation/frontend/*` vs `PRESENTATION_UX_SPEC.md`) is handled in Checkpoint 3.
