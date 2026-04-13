# Development Prompt: UI Rendering Performance

Use this prompt to execute implementation work from `docs/roadmap/TASKS/ui-rendering-performance-plan.md`.

## Prompt

You are implementing the DocMap presentation UI rendering performance plan.

Context:
- Read and follow `docs/roadmap/TASKS/ui-rendering-performance-plan.md`.
- Respect project invariants from `docs/agent/PROJECT_CONSTITUTION.md`.
- Presentation runtime is read-only and must not introduce writes outside existing boundaries.

Implementation scope:
1. Execute Phase A fully, including code changes and verification.
2. If Phase A acceptance criteria pass, execute Phase B.
3. Stop before Phase C unless explicitly instructed to continue.

Mandatory requirements:
- Keep behavior deterministic.
- Keep API backward compatible; only additive query params are allowed.
- Update docs when contracts/behavior change.
- Use smallest safe change set for each phase.
- Do not perform unrelated cleanup.

Phase A requirements:
- Frontend startup must no longer block on boundaries fetch.
- Locations render first; boundaries hydrate in background.
- Add in-process boundaries cache in presentation backend with TTL (10 minutes).
- Add minimal timing instrumentation around boundaries generation/fetch path.
- Maintain error handling clarity (startup errors vs boundaries-only errors).

Phase B requirements:
- Add `rank_filter=default|all` and `geometry_detail=low|full` to boundaries API.
- Default behavior must use reduced ranks and low detail.
- Integrate deterministic low-detail boundary artifact path.
- Keep operator/debug path to full/all variants.

Verification requirements:
- Record and report:
  - first meaningful render timestamp
  - boundaries-ready timestamp
  - boundaries payload size (encoded/decoded) per variant
  - endpoint latency cold/warm
- Include what was verified and what was not verified.

Output format:
1. Summary of implemented changes by phase.
2. File-by-file change list.
3. Verification results with concrete numbers.
4. Residual risks and next recommended step.

