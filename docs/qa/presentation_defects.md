# Presentation Defect Log

## Confirmed Defects

### DEF-PRES-001
- `defect_id`: DEF-PRES-001
- `title`: Location-document fallback query allowed non-fallback ranks (`continent`/`ocean`) to resolve documents
- `severity`: high
- `area`: presentation backend / API contract
- `requirement_violated`: `R-EXCL-004`, `R-API-003`
- `reproduction_steps`:
  1. Inspect `services/presentation/backend/repository.py::resolve_location_for_documents`.
  2. Observe candidate fallback set came from full `bi_location_hierarchy` ancestor chain with no rank filter.
  3. Under datasets where non-city ancestors have documents, endpoint can resolve through non-allowed ranks.
- `expected_behavior`: fallback path must remain constrained to `city -> admin_region/region -> country` only.
- `actual_behavior`: SQL had no rank allowlist and could include all ancestor ranks.
- `likely_root_cause`: fallback SQL selected by depth+docs without rank-class filter.
- `files_components_involved`: `services/presentation/backend/repository.py`
- `status`: fixed
- `fix_summary`: added rank guard in candidate and ancestor selection so only `city/admin_region/region/country` are eligible.

### DEF-PRES-002
- `defect_id`: DEF-PRES-002
- `title`: PDF thumbnail click bubbled to card click handler and produced unstable pin toggle behavior
- `severity`: medium
- `area`: presentation frontend / document card interactions
- `requirement_violated`: `R-PANEL-008`, `R-PANEL-009`, `R-PANEL-007`
- `reproduction_steps`:
  1. Open presentation UI.
  2. Search for a location with document results (for example `paris`).
  3. Click a card PDF thumbnail button.
  4. Observe modal open and pinned-state behavior around card click interaction was coupled to card handler bubbling.
- `expected_behavior`: thumbnail click should execute thumbnail action only (pin/open modal) and not trigger parent card toggle logic.
- `actual_behavior`: click event propagated to parent card handler.
- `likely_root_cause`: thumbnail button lacked explicit propagation stop before invoking parent-supplied callback.
- `files_components_involved`: `services/presentation/frontend/src/PdfThumbnail.tsx`, `services/presentation/frontend/src/App.tsx`
- `status`: fixed
- `fix_summary`: stop event propagation in thumbnail button handler before invoking `onClick` callback.

## Spec Ambiguities

### AMBIG-PRES-001
- Docs in `docs/presentation/PRESENTATION_ARCHITECTURE.md` and `PRESENTATION_DATA_CONTRACT.md` describe current behavior as not strictly enforcing fallback rank allowlist, while phase/task authority requires preserved strict fallback semantics (`city -> region -> country`).
- Resolution used in this QA cycle: treat phase/task + architecture invariants as authoritative and enforce rank guard in implementation.

## Deferred Non-Blocking Improvements

### IMP-PRES-001
- FastAPI startup uses deprecated `@app.on_event("startup")`; migration to lifespan handlers is recommended but non-blocking for current presentation functional compliance.
