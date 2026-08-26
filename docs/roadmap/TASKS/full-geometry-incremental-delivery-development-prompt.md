# Development Prompt: Full Geometry Incremental Delivery

Use this prompt to execute implementation work from `docs/roadmap/TASKS/full-geometry-incremental-delivery-plan.md`.

## Prompt

You are implementing the DocMap presentation full-geometry incremental delivery plan.

Context:
- Read and follow `docs/roadmap/TASKS/full-geometry-incremental-delivery-plan.md`.
- Respect project invariants from `docs/agent/PROJECT_CONSTITUTION.md`.
- Presentation runtime is read-only and must not introduce writes outside existing boundaries.
- Full stored geometry must remain canonical for presentation delivery.

Primary objective:
- Remove low-geometry delivery mode entirely.
- Keep only full stored geometry.
- Prevent browser overload by fetching and rendering only currently relevant polygons.

Implementation scope:
1. Execute Phase A fully.
2. If Phase A acceptance criteria pass, execute Phase B.
3. If Phase B acceptance criteria pass, execute Phase C.
4. Stop before Phase D unless explicitly instructed to continue.

Mandatory requirements:
- Remove `geometry_detail` from presentation API/frontend/runtime behavior.
- Do not introduce new geometry simplification code paths.
- Do not introduce low-detail artifact serving.
- Keep behavior deterministic.
- Keep docs/tests aligned with the new contract in the same change set.
- Use the smallest safe change set for each phase.
- Do not perform unrelated cleanup.

Phase A requirements:
- remove `geometry_detail` query parameter and related types/tests/docs
- add scoped boundaries query shape (`bbox`, `ranks`, `selected_location_id`, `highlighted_location_ids`)
- update in-process cache keying to match new request shape

Phase B requirements:
- implement backend spatial filtering for `bi_admin_boundaries`
- preserve full stored geometry in responses
- include explicit selected/highlighted ids even outside viewport scope

Phase C requirements:
- no startup boundary fetch before viewport is known
- fetch scoped polygons after viewport arrives
- debounce viewport-driven requests
- keep previous polygon state until replacement response is ready

Verification requirements:
- record and report:
  - startup first meaningful render timing
  - first scoped boundary request timing
  - payload size and feature count for representative viewport/rank requests
  - whether browser console stays free of polygon allocation failures
  - whether selected/highlighted polygon inclusion works
- include what was verified and what was not verified

Output format:
1. Summary of implemented changes by phase.
2. File-by-file change list.
3. Verification results with concrete numbers.
4. Residual risks and next recommended step.

