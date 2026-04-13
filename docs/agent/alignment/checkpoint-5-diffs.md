# Checkpoint 5 Diffs (Pipeline/Domain)

Date: 2026-03-29

## Resolved in this checkpoint

1. `docs/architecture/PIPELINE.md` did not explicitly state geocode option interaction in unprocessed mode.
- Code truth: when `process_unprocessed_only=true`, orchestrator ignores `refresh_geo_identity` and `full_refresh_geo_information`.

2. `docs/architecture/PIPELINE.md` did not explicitly state geocode resume canonical-refresh behavior.
- Code truth: resumed geocode stage (`current_index > 0`) skips canonical dictionary refresh during that resumed execution.

3. `docs/architecture/PIPELINE.summary.md` lacked the two nuanced runtime semantics above.
- Summary updated to reflect current orchestrator behavior.

## Reviewed and confirmed aligned

- architecture/data-model/service-boundary docs vs SQL and service ownership
- operations/config/development/verification runbooks vs compose/env/runtime entrypoints
