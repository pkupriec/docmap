# Control UI Specification

## Purpose

The Control UI is an operator-facing control plane for DocMap pipeline execution.

It must support:

- start pipeline run
- cancel active run
- retry run
- retry stage
- monitor run status
- monitor progress
- follow logs

This UI is internal operator tooling.

No authentication or RBAC is required in phase 10.

---

# High-Level Layout

The UI consists of 3 main areas:

1. Header
2. Runs List view
3. Run Details view

The Live Logs panel is part of Run Details.

Suggested layout:

- left side: Runs List
- right side: Run Details
- bottom-right: Live Logs

Desktop-first layout is sufficient for phase 10.

---

# Header

The header contains:

- title: "DocMap Control Plane"
- Start Run button
- active run status badge
- backend connectivity indicator

The header must remain visible at all times.

---

# View 1 — Runs List

## Purpose

Shows historical and current pipeline runs.

## Component type

Simple table.

## Columns

- Run ID
- Pipeline Type
- Status
- Current Stage
- Progress Summary
- Started At
- Finished At

## Behavior

- auto-refresh every 5 seconds
- highlight active run
- selecting a row opens Run Details
- newest runs first

## Progress Summary rendering

If progress exists:

- document-oriented stages:
  `134 / 812`
- generic stages:
  `87 / 203`

If progress is unavailable:

- show `—`

---

# View 2 — Run Details

## Purpose

Shows full details for the selected run.

## Sections

### 1. Run Summary Card

Fields:

- Run ID
- Pipeline Type
- Status
- Current Stage
- Target Scope
- Started At
- Finished At
- Error Message, if any

### 2. Command Actions

Buttons:

- Cancel Run
- Retry Run

These buttons must be visible for all selected runs.

The backend enforces final validity rules.

When action is not valid, UI may disable the button or allow submission and show API error.

### 3. Stages Table

Columns:

- Stage Order
- Stage Name
- Status
- Items Completed
- Items Failed
- Started At
- Finished At
- Retry Action

Retry Action:

- one Retry button per stage

### 4. Progress Panel

Shows current progress rows from `pipeline_progress`.

Render rules:

- if `current_document_url` exists, show document link
- if `current_item_label` exists, show label
- always show:
  - current index
  - total items
  - items completed
  - items failed
  - updated at
  - message

---

# View 3 — Live Logs

## Purpose

Operator log tail.

## Component type

Scrollable panel.

## Behavior

- uses SSE endpoint for the selected run
- autoscroll enabled by default
- pause autoscroll toggle
- preserve existing logs during reconnect
- append new logs in ascending id order

## Filters

Provide client-side filters:

- level
- stage_name
- service_name

## Log line format

Recommended format:

`[timestamp] [level] [service] [stage] message`

Examples:

`[2026-03-08T12:00:00Z] [INFO] [pipeline] [extract] Stage started`
`[2026-03-08T12:01:04Z] [WARN] [extractor] [extract] Missing field in response`

---

# Start Run Modal

## Purpose

Submit a `start_run` command.

## Fields

### Required

- Pipeline Type
- Target Scope

### Optional, depending on target scope

- Document URL
- Document Range Start
- Document Range End
- Options JSON

## Pipeline Type select values

- full_pipeline
- crawl_only
- extract_only
- geocode_only
- analytics_only
- export_only

## Target Scope select values

- all
- single_document
- document_range
- incremental

## Submit behavior

Submit to:

`POST /api/runs`

On success:

- show returned command id
- refresh runs list
- close modal

On error:

- show inline error

---

# Cancel Run Action

## Trigger

Button in Run Details.

## API

`POST /api/runs/{run_id}/cancel`

## UX

- ask for confirmation
- after success, refresh run details
- keep logs visible

---

# Retry Run Action

## Trigger

Button in Run Details.

## API

`POST /api/runs/{run_id}/retry`

## UX

- ask for confirmation
- explain that retry creates a new run
- after success, refresh runs list

---

# Retry Stage Action

## Trigger

Button in stage row.

## API

`POST /api/runs/{run_id}/stages/{stage_name}/retry`

## UX

- ask for confirmation
- explain that downstream stages are also reset
- after success, refresh run details

---

# SSE Integration

## Endpoint

`GET /api/runs/{run_id}/events`

## Event types

- run_status
- stage_status
- progress
- log
- heartbeat

## Client rules

When selected run changes:

1. close previous EventSource
2. load fresh REST snapshot
3. open new EventSource

On SSE disconnect:

- show "Reconnecting…" status
- retry automatically
- do not clear visible logs

---

# REST Bootstrap Sequence

When opening a run:

1. `GET /api/runs/{run_id}`
2. `GET /api/runs/{run_id}/stages`
3. `GET /api/runs/{run_id}/progress`
4. `GET /api/runs/{run_id}/logs?limit=200`

Then start SSE.

SSE is for incremental updates only.

---

# Empty States

## No runs

Show:

- "No pipeline runs yet"
- primary CTA: "Start Run"

## No logs

Show:

- "No logs for this run"

## No progress

Show:

- "No progress reported yet"

---

# Error States

The UI must show inline error messages for:

- failed REST requests
- failed command submission
- SSE disconnects
- invalid state transitions returned by API

Do not hide backend errors silently.

---

# Styling Guidance

Phase 10 UI should be simple and utilitarian.

Use:

- clear tables
- badges for statuses
- monospace font for logs
- no advanced dashboard visualizations

Suggested status badge mapping:

- pending: gray
- running: blue
- cancelling: orange
- cancelled: gray
- failed: red
- success: green

---

# Out of Scope

Do not implement:

- authentication
- permissions
- scheduling
- queue management UI
- multi-run comparison dashboards
- charts
- mobile-first layouts