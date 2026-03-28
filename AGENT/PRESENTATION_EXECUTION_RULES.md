# Presentation Execution Rules

This file is a presentation-specific routing and constraint reference. It is not the default global preload.

Read in this order for presentation tasks:

1. `AGENT/INDEX.md`
2. `AGENT/PROJECT_CONSTITUTION.md`
3. `AGENT/EXECUTION_MODEL.md`
4. `AGENT/CURRENT_PHASE.md`
5. `PRESENTATION.summary.md`
6. the specific `PRESENTATION_*` docs relevant to the task
7. the matching `TASKS/` brief only if the task is phase- or handoff-specific

Presentation invariants:

- presentation is an independent read-only service
- backend reads BI/runtime tables and serves deterministic API responses
- frontend preserves current hover, pin, search, PDF, and map interaction semantics unless the user explicitly changes them
- hierarchy fallback remains `city -> region -> country`
- `continent` and `ocean` are rendering classes, not new fallback targets
- runtime geometry generation or mutation does not belong in presentation

When touching presentation:

- use `PRESENTATION_ARCHITECTURE.md` for runtime/data boundaries
- use `PRESENTATION_DATA_CONTRACT.md` and `PRESENTATION_API_SPEC.md` for payload/API authority
- use `PRESENTATION_UX_SPEC.md` for interaction semantics
- use `PRESENTATION_IMPLEMENTATION_PLAN.md` and task briefs for scoped phase intent

Forbidden moves:

- merging presentation into the control-plane UI/runtime
- adding presentation write behavior
- bypassing BI/runtime inputs with direct pipeline-stage logic
- extending fallback beyond the documented model without explicit user approval
