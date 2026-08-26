# Development Prompt: Presentation Runtime Performance Remediation

Use this prompt to execute implementation work from `docs/roadmap/TASKS/presentation-runtime-performance-remediation-plan.md`.

## Prompt

You are implementing the DocMap presentation runtime performance remediation plan.

Context:
- Read and follow `docs/roadmap/TASKS/presentation-runtime-performance-remediation-plan.md`.
- Respect project invariants from `docs/agent/PROJECT_CONSTITUTION.md`.
- Presentation runtime remains read-only; move stable expensive work into analytics/build/startup preparation only where ownership is explicit.

Execution model:
1. Execute one phase at a time in the documented order.
2. Measure before and after for the phase you are changing.
3. Stop after the current phase unless explicitly instructed to continue.
4. Keep changes minimal and focused on the active phase.

Mandatory requirements:
- keep behavior deterministic
- do not broaden scope into unrelated cleanup
- keep docs, schema/migrations, and code aligned in the same change set when behavior or runtime assumptions change
- explicitly call out anything that should be baked ahead instead of kept in runtime

Phase priorities:
- start with Phase A
- Phase B and later require evidence from the measured baseline
- do not jump to renderer-level fixes before backend connection/query/index work is measured

When evaluating whether work should move out of runtime, use this rule:
- if the value is stable, deterministic, repeatedly recomputed, and owned by analytics/build/startup preparation, prefer baking it ahead rather than recalculating it in request or interaction hot paths

Output format:
1. Phase executed
2. Summary of changes
3. What was measured before and after
4. What was moved or recommended to move out of runtime
5. Residual risks
6. Next recommended phase
