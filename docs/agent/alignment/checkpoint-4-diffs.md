# Checkpoint 4 Diffs (Control UI)

Date: 2026-03-28

## Resolved in this checkpoint

1. Header spec required backend connectivity indicator.
- Code truth: no connectivity indicator exists; only active-run badge is rendered.

2. Runs List spec included `Progress Summary` column and active-run row highlight.
- Code truth: table has no progress-summary column; selected run row is highlighted.

3. Stage table spec omitted Resume action.
- Code truth: UI includes both Retry and Resume; Resume is conditionally enabled.

4. Start Run modal spec referenced free-form `Options JSON`.
- Code truth: modal exposes structured fields and a specific `full_refresh_geo_information` checkbox only when supported.

5. Process Unprocessed spec forced fixed payload (`full_pipeline` + `all`).
- Code truth: dedicated modal allows user-selected `pipeline_type` and `target_scope` while always setting `options.process_unprocessed_only=true`.

6. REST bootstrap sequence in spec requested separate stages/progress endpoints.
- Code truth: UI calls `GET /runs/{id}` (run+stages+progress) and then logs endpoint.

7. Start success spec said UI shows returned command id.
- Code truth: UI refreshes runs and closes modal without separately displaying command id.
