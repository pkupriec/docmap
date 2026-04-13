# Checkpoint 1 Diffs (Control Backend)

Date: 2026-03-28

## Resolved in this checkpoint

1. `docs/api/CONTROL_API.md` lacked explicit validation error semantics for `POST /runs`.
- Code truth: invalid `pipeline_type`/`target_scope` returns `409 invalid_request`; duplicate start payload returns `409 duplicate_command`.

2. `docs/api/CONTROL_API.md` did not describe `retry` payload merge behavior.
- Code truth: retry creates a new run using target run type/scope and merges request options into run parameters.

3. `docs/api/CONTROL_API.md` did not define `last_event_id` runtime behavior.
- Code truth: `last_event_id` is parsed as integer log cursor; parse failures fall back to `0`.

4. `docs/api/CONTROL_API.md` did not call out deferred-command behavior under active run.
- Code truth: orchestrator marks active run `cancelling` and defers start/retry/retry-stage commands.

5. `docs/api/CONTROL_API.openapi.yaml` option list omitted `full_refresh_geo_information`.
- Code truth: orchestrator reads this option and can force full cache re-geocode.

6. `docs/api/CONTROL_API.openapi.yaml` lacked `last_event_id` cursor description.
- Code truth: cursor tracks persisted `pipeline_logs.id`.

## Deferred (out of checkpoint scope)

- Control UI documentation consistency (`docs/api/CONTROL_UI.md`) will be handled in Checkpoint 4.
