# Development Prompt: Chunked Boundary Delivery

Use this prompt to execute implementation work from `docs/roadmap/TASKS/chunked-boundary-delivery-plan.md`.

## Prompt

You are implementing the DocMap presentation chunked boundary delivery plan.

Context:
- Read and follow `docs/roadmap/TASKS/chunked-boundary-delivery-plan.md`.
- Respect project invariants from `docs/agent/PROJECT_CONSTITUTION.md`.
- Presentation runtime is read-only and must not introduce writes outside existing ownership boundaries.
- Full stored geometry must remain canonical for presentation delivery.
- Do not reintroduce low-detail geometry, simplification, or decimation paths.

Primary objective:
- make polygon delivery behave more like a slippy-map system
- reduce polygon payload and request churn by using chunked or stable quantized delivery
- preserve correctness of geometry and explicit selected/highlighted polygon reveal

Implementation scope for the next session:
1. Execute Phase A fully.
2. If Phase A acceptance criteria pass, execute Phase B.
3. If Phase B acceptance criteria pass, execute the smallest safe slice of Phase C.
4. Stop before any renderer replacement work.

Mandatory requirements:
- preserve full stored geometry as the only served geometry
- separate viewport polygon loading from explicit selected/highlighted polygon loading
- prefer stable chunk ids; if that is too large for one session, implement quantized viewport buckets as the stepping stone
- keep deterministic request shapes and deterministic ordering
- keep visible polygons rendered until replacement chunk data is ready
- prevent stale async chunk responses from overwriting newer state
- update docs/tests in the same change set
- do not perform unrelated cleanup

Phase A requirements:
- split frontend boundary flow into viewport loading and explicit focus loading
- avoid full viewport boundary reload when only selected/highlighted state changes
- keep additive merge behavior by `location_id`

Phase B requirements:
- define stable spatial chunk ids or quantized viewport bucket identities
- key backend and frontend caches by those stable identities
- ensure small pans reuse cache instead of missing on raw float bbox churn

Phase C minimum requirements:
- add backend read-path support for chunk/bucket queries
- preserve explicit inclusion behavior outside current viewport chunk scope
- avoid duplicate polygon emission for the same `location_id`

Verification requirements:
- record and report:
  - chunk/bucket identities requested for representative zoom levels
  - feature counts and payload sizes by chunk/bucket request
  - whether selection/highlight triggers only explicit polygon fetches
  - whether pan/zoom causes incremental loading instead of whole-set replacement
  - whether browser behavior remains flicker-free and allocation-safe
- include what was verified and what was not verified

Output format:
1. Summary of implemented changes by phase.
2. File-by-file change list.
3. Verification results with concrete numbers.
4. Residual risks and next recommended step.
