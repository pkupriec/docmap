# Development Prompt: Multi-Chunk Boundary Delivery

Use this prompt to execute implementation work from `docs/roadmap/TASKS/multi-chunk-boundary-delivery-plan.md`.

## Prompt

You are implementing the DocMap presentation multi-chunk boundary delivery plan.

Context:
- Read and follow `docs/roadmap/TASKS/multi-chunk-boundary-delivery-plan.md`.
- Respect project invariants from `docs/agent/PROJECT_CONSTITUTION.md`.
- Presentation runtime is read-only and must not introduce writes outside existing ownership boundaries.
- Full stored geometry must remain canonical for presentation delivery.
- The current baseline already has:
  - separate viewport vs explicit polygon loading
  - stable quantized `viewport_bucket` support
  - additive merge by `location_id`
  - stale async response guards

Primary objective:
- move from single `viewport_bucket` requests to a multi-chunk request set
- retain and prune chunk payloads client-side instead of replacing the whole viewport payload
- add browser-level regression coverage proving:
  - pan/zoom fetches only newly needed chunks
  - selection/highlight does not trigger viewport chunk reloads

Implementation scope:
1. Execute Phase A fully.
2. If Phase A acceptance criteria pass, execute Phase B.
3. If Phase B acceptance criteria pass, execute Phase C.
4. If Phase C acceptance criteria pass, execute Phase D.
5. Stop before any renderer replacement or unrelated cleanup.

Mandatory requirements:
- keep full stored geometry as the only geometry served by presentation
- do not introduce simplification, decimation, or low-detail geometry modes
- keep viewport chunk loading separate from explicit selected/highlighted polygon loading
- keep merge behavior keyed by `location_id`
- prevent stale async chunk responses from overwriting newer state
- keep currently visible polygons rendered until replacement chunk data is ready
- keep ordering deterministic for identical chunk request shapes
- update docs/tests in the same change set when contracts or behavior change

Phase A requirements:
- define deterministic chunk ids by zoom band
- derive sorted canonical chunk-id sets from viewport + margin
- add backend parsing/normalization for `chunk_ids`
- key caches by stable chunk-id identities rather than raw float churn

Phase B requirements:
- support backend reads by `chunk_ids`
- preserve explicit inclusion outside current viewport chunk scope
- suppress duplicate polygon emission for the same `location_id`

Phase C requirements:
- replace single viewport-boundary state with chunk-diffed client cache state
- fetch only missing chunks during ordinary pan/zoom
- retain loaded visible chunks while new chunks are in flight
- prune stale chunks conservatively
- ensure selection/highlight changes do not force viewport chunk refetch

Phase D requirements:
- add browser-level regression coverage around network/request behavior
- verify pan/zoom requests only new chunks when overlap exists
- verify selection/highlight triggers only explicit polygon fetches
- verify viewport chunk requests are not reissued solely because focus state changed

Verification requirements:
- run targeted backend/frontend tests for changed contract behavior
- run browser-level regression coverage if implemented
- record and report:
  - representative chunk ids by zoom level
  - number of chunk requests during startup/pan/zoom/focus changes
  - feature counts and payload sizes for representative chunk requests
  - whether visible polygons remained rendered during refresh
  - what was verified vs not verified

Output format:
1. Summary of implemented changes by phase.
2. File-by-file change list.
3. Verification results with concrete numbers.
4. Residual risks and next recommended step.
