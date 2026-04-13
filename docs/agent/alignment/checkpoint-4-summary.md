# Checkpoint 4 Summary (Control UI Behavior)

Date: 2026-03-28

## Scope Reviewed

Code:
- `ui/src/App.jsx`
- `ui/src/main.jsx`
- `ui/src/styles.css`

Docs:
- `docs/api/CONTROL_UI.md`
- `docs/api/CONTROL_API.md` (validation only)

## Alignment Outcome

Checkpoint 4 aligned control UI documentation to current frontend behavior. No `ui/*` code changes were required.

Updated docs:
- `docs/api/CONTROL_UI.md`

## Behavior Facts Locked

- Header includes title, Start Run, Process Unprocessed, and active-run badge; no backend-connectivity indicator is implemented.
- Runs table columns are `Run ID`, `Pipeline`, `Status`, `Current Stage`, `Started`, `Finished`; selected row is highlighted.
- Stage table provides both `Retry` and `Resume`, where Resume is enabled only for partially completed, non-success stages.
- Start/Process-Unprocessed use modal forms; there is no free-form options JSON editor.
- Process-Unprocessed modal allows operator-selected pipeline/scope and sets `options.process_unprocessed_only=true`.
- Run bootstrap calls `GET /runs/{id}` (already includes stages/progress) then `GET /runs/{id}/logs?limit=200`.
- Start modal success behavior is refresh + close; returned command id is not separately shown in UI.

## Ready For

Checkpoint 5: pipeline/domain service docs alignment (`architecture/*`, `operations/*`) against runtime code.
