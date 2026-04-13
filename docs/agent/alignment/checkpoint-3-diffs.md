# Checkpoint 3 Diffs (Presentation Frontend)

Date: 2026-03-28

## Resolved in this checkpoint

1. `docs/presentation/PRESENTATION_UX_SPEC.md` performance note claimed startup waits on full boundaries payload.
- Code truth: frontend calls `/api/map/boundaries?lite=1` during startup (`services/presentation/frontend/src/api.ts`) and waits for locations + lite boundaries together.

## Reviewed and confirmed aligned

- left-panel collapse behavior and compact quick actions.
- right-panel mode precedence and search override behavior.
- search debounce and 3+ trimmed-character activation.
- document hover/pin visualization semantics.
- PDF modal open/close interaction semantics, including `Esc`.
- viewport-driven link visibility and offscreen count behavior.
- geometry rendering and fallback rules, including city zoom threshold `3.2`.
