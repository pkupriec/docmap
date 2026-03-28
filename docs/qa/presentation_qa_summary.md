# Presentation QA Summary

## Scope Executed
- Spec-driven QA cycle completed for presentation layer across:
  - presentation backend API contract behavior
  - presentation frontend interaction behavior
  - mixed-geometry and fallback semantics validation
  - read-only architecture constraints

Artifacts created:
- `docs/qa/presentation_requirements_checklist.md`
- `docs/qa/presentation_test_cases.md`
- `docs/qa/presentation_defects.md`
- `docs/qa/presentation_qa_summary.md`

## What Was Tested
- Automated tests:
  - `tests/test_presentation_api.py`
  - `tests/test_presentation_repository.py` (new)
  - `tests/test_analytics_geometry_assets.py`
  - `tests/test_analytics_service.py`
- Runtime/API checks:
  - `/healthz`
  - `/api/map/locations`
- Browser-driven manual/E2E checks via Playwright:
  - startup load state -> ready state
  - search activation and results rendering
  - document card and PDF modal interactions
  - clear/reset flows and pinned visualization behavior

## Initial Failures / Defects Found
1. `DEF-PRES-001` fallback query did not constrain rank ladder and could resolve via non-allowed ranks.
2. `DEF-PRES-002` thumbnail click propagated into parent card click logic.

## Fixes Implemented
1. Backend fallback guard
- File: `services/presentation/backend/repository.py`
- Change: added rank filtering in fallback candidate SQL to allow only `city/admin_region/region/country` for requested node and ancestors.

2. Frontend thumbnail click isolation
- File: `services/presentation/frontend/src/PdfThumbnail.tsx`
- Change: thumbnail button now stops click propagation before executing thumbnail callback.

3. Regression coverage
- File: `tests/test_presentation_repository.py` (new)
- Change: added test validating fallback SQL enforces rank allowlist intent.

## Re-Test Results
- Automated re-test result: pass
  - `15 passed` on targeted presentation+analytics-related test suite.
- Browser re-test result: pass for validated interaction path
  - thumbnail click opens modal and preserves pinned-document behavior after modal close.

## Defect Status
- `DEF-PRES-001`: fixed
- `DEF-PRES-002`: fixed
- `AMBIG-PRES-001`: open as documentation ambiguity (implementation aligned to stricter phase authority)

## Remaining Blockers
- None blocking presentation QA cycle completion.

## Assumptions Used
- Phase/task authority requiring fallback restriction was treated as binding over weaker "current behavior" notes.
- Existing repository worktree was pre-dirty; unrelated changes were not modified or reverted.

## Exact Commands Used
```powershell
Get-ChildItem -Name
Get-Content -Raw <spec/docs/files>
Get-ChildItem -Recurse -File services/presentation/backend | Select-Object -ExpandProperty FullName
Get-ChildItem -Recurse -File services/presentation/frontend/src | Select-Object -ExpandProperty FullName
Get-ChildItem -Recurse -File tests | Select-Object -ExpandProperty FullName
python -m pytest -q tests/test_presentation_api.py
python -m pytest -q tests/test_analytics_geometry_assets.py tests/test_analytics_service.py
python -m pytest -q tests/test_presentation_api.py tests/test_presentation_repository.py tests/test_analytics_geometry_assets.py tests/test_analytics_service.py

docker compose -f infra/docker-compose.yml up -d postgres presentation
docker compose -f infra/docker-compose.yml up -d --build presentation
curl.exe -sS http://localhost:8080/healthz
curl.exe -sS http://localhost:8080/api/map/locations

# Playwright MCP actions executed:
# browser_navigate, browser_wait_for, browser_fill_form, browser_click,
# browser_press_key, browser_snapshot, browser_evaluate
```
