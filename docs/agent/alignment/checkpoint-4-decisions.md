# Checkpoint 4 Decisions

Date: 2026-03-28

## D4-1: UI implementation is canonical for operator workflow docs

Decision: Align `CONTROL_UI.md` to implemented `ui/src/App.jsx` interactions rather than preserving aspirational phase text.

Rationale: this phase requires behavior documentation to reflect current runtime, with code as source of truth.

## D4-2: Keep structured modal options documentation

Decision: Document current explicit controls (`process_unprocessed_only`, `full_refresh_geo_information`) instead of generic options JSON editing.

Rationale: explicit controls reduce ambiguity and match actual UI contract.

## D4-3: Preserve bootstrap simplification

Decision: Document `GET /runs/{id}` + logs bootstrap flow (without separate stages/progress fetch calls).

Rationale: run detail endpoint already includes stages/progress in current API behavior.
