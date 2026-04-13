# Checkpoint 2 Summary (Presentation Backend Contracts)

Date: 2026-03-28

## Scope Reviewed

Code:
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`
- `services/presentation/backend/schemas.py`
- `main_presentation.py`
- `tests/test_presentation_api.py`
- `tests/test_presentation_repository.py`

Docs:
- `docs/presentation/PRESENTATION_API_SPEC.md`
- `docs/presentation/PRESENTATION_DATA_CONTRACT.md`
- `docs/presentation/PRESENTATION_ARCHITECTURE.md`
- `docs/presentation/PRESENTATION_UX_SPEC.md` (validation only)

## Alignment Outcome

Checkpoint 2 aligned presentation backend contract docs to current runtime behavior; code was not modified.

Updated docs:
- `docs/presentation/PRESENTATION_API_SPEC.md`
- `docs/presentation/PRESENTATION_DATA_CONTRACT.md`
- `docs/presentation/PRESENTATION_ARCHITECTURE.md`

## Behavior Facts Locked

- Not-found behavior differs by endpoint type:
  - single-document endpoints return `404 {"error":"not_found"}`
  - location-documents endpoint returns `200` with empty scoped payload when unresolved.
- Search endpoint validates `q` as non-empty, but repository returns empty arrays for trimmed queries shorter than 3.
- Location-document scope is city-filtered only for `city`; non-city scope uses hierarchy descendants without extra rank filtering.
- Presentation backend remains read-only and serves PDFs with byte-range support (`200`/`206`/`416` semantics).

## Ready For

Checkpoint 3: presentation frontend behavior alignment against UX/API docs.
