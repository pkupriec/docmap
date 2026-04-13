# Checkpoint 0 Decisions

Date: 2026-03-28

## D0-1: Source-of-truth precedence

Decision: Use SQL/infra/runtime code over documentation when conflicts are found.

Rationale: `docs/index.md` explicitly defines this precedence.

## D0-2: Frontend separation

Decision: Evaluate `ui/` and `services/presentation/frontend/` as separate products with separate docs contracts.

Rationale: They map to different runtimes and APIs (control vs presentation).

## D0-3: Context-window control

Decision: Use checkpoint artifact files in `TASKS/alignment/` as the persistent handoff mechanism.

Rationale: Full repo cannot be safely ingested in one window without context drift.

## D0-4: Exclusion rules

Decision: Exclude `node_modules`, build outputs, caches, and compiled artifacts from alignment scanning.

Rationale: They are generated/vendor content and not normative source behavior.
