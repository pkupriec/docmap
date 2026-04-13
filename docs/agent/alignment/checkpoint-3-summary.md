# Checkpoint 3 Summary (Presentation Frontend Behavior)

Date: 2026-03-28

## Scope Reviewed

Code:
- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/PdfThumbnail.tsx`
- `services/presentation/frontend/src/api.ts`
- `services/presentation/frontend/src/types.ts`
- `services/presentation/frontend/src/styles.css`
- `services/presentation/frontend/src/main.tsx`

Tests (behavior evidence):
- `tests/test_presentation_api.py`

Docs:
- `docs/presentation/PRESENTATION_UX_SPEC.md`
- `docs/presentation/PRESENTATION_API_SPEC.md` (validation only)
- `docs/presentation/PRESENTATION_DATA_CONTRACT.md` (validation only)

## Alignment Outcome

Checkpoint 3 aligned presentation UX documentation to frontend runtime behavior; no frontend code changes were required.

Updated docs:
- `docs/presentation/PRESENTATION_UX_SPEC.md`

## Behavior Facts Locked

- Startup waits for `locations` and `boundaries` together, where boundaries are fetched in lite mode (`/api/map/boundaries?lite=1`).
- Search activation is 3+ trimmed characters with ~180ms debounce and API cap of 5 results per type.
- Right panel remains search-driven while search is active even when map hover/pin changes.
- `Esc` clears pinned location/document and closes PDF modal if open.
- Document-link rendering is viewport-sensitive with optional declutter (`top 12` visible links).
- Geometry behavior matches implemented rank and zoom rules (city polygon threshold `>= 3.2`, non-city polygon fallback to points when boundary missing).

## Ready For

Checkpoint 4: control UI (`ui/*`) behavior alignment with control UI docs.
