# Phase 10 — Pipeline Control Plane and Monitoring UI

## Objective

Introduce a lightweight operator control plane for DocMap pipelines.

The control plane provides:

* pipeline run management
* pipeline stage retry
* cancellation
* live monitoring
* live log streaming

The control plane is implemented as:

* FastAPI backend integrated into the existing Python application
* React UI frontend
* operational metadata stored in Postgres
* SSE event stream for live updates

This phase introduces **control capabilities**, not only monitoring.

---

# Scope

This phase implements:

Operator UI capabilities:

* start pipeline run
* cancel run
* retry entire run
* retry individual stage
* view pipeline runs
* view pipeline stages
* view pipeline progress
* view live logs

Backend capabilities:

* command API
* SSE event stream
* monitoring queries
* command queue execution

Database additions:

* pipeline_commands
* pipeline_logs
* pipeline_progress

---

# Non-Goals

This phase does NOT implement:

* multi-user authentication
* scheduling
* pipeline definition editing
* arbitrary DAG editing
* pause/resume execution
* multiple concurrent runs
* distributed command workers
* external logging stacks

---

# Core Architecture

The control plane consists of four layers:

Pipeline runtime

* executes stages
* writes progress
* writes logs
* reads commands

Command queue

* pipeline_commands table
* command lifecycle management

Control API

* REST endpoints
* SSE events

Operator UI

* React interface
* command submission
* monitoring views

---

# Single Active Run Policy

The system allows only **one active pipeline run at a time**.

Active statuses:

* pending
* running
* cancelling

If a start_run command is issued while a run is active:

1. the active run enters `cancelling`
2. the system waits for the current item to finish
3. a new run is created
4. execution continues with the new run

Duplicate start commands with identical payload may be rejected.

---

# Command Model

All commands are written to a single queue table:

pipeline_commands

Allowed commands:

* start_run
* cancel_run
* retry_run
* retry_stage

Commands are never executed directly by HTTP handlers.

API writes command records.

Orchestrator polls and executes them.

---

# Command Execution Model

Execution loop:

* poll pipeline_commands
* select pending commands
* process in ascending id order

Command lifecycle:

pending → accepted → applied / rejected / failed

Guarantees:

* commands processed once
* row-level locking prevents double processing
* only one mutating command per run at a time

Polling interval:

1 second

---

# Command Semantics

## cancel_run

Soft cancel.

Process:

run.status → cancelling

current item completes

run.status → cancelled

---

## retry_run

Creates a new pipeline run.

Original run remains unchanged.

If run is active:

cancel → new run created

---

## retry_stage

Resets the specified stage and all downstream stages.

Upstream stages remain unchanged.

If run is active:

cancel → restart from stage

---

# Pipeline Types

Each run must specify a pipeline_type.

Allowed values:

* full_pipeline
* crawl_only
* extract_only
* geocode_only
* analytics_only
* export_only

No pipeline definition table is introduced in this phase.

---

# Run Status Model

Allowed run statuses:

pending
running
cancelling
cancelled
failed
success

Only one stage may be running at any time.

---

# Stage Status Model

pending
running
success
failed
skipped

---

# Command Status Model

pending
accepted
applied
rejected
failed

---

# Progress Model

pipeline_progress stores current state only.

One row per:

pipeline_run_id + stage_name

Fields:

* current_index
* total_items
* items_completed
* items_failed
* current_document_id
* current_document_url
* current_item_label
* message
* updated_at

---

# Logging

Primary operator logs are stored in:

pipeline_logs

Stdout is used only for startup and fatal errors.

Log retention policy:

keep logs for the most recent **10 pipeline runs**

Older logs may be deleted.

---

# SSE Event Stream

Endpoint:

GET /api/runs/{run_id}/events

Event types:

* run_status
* stage_status
* progress
* log
* heartbeat

Backend uses polling of Postgres.

No Redis or message bus.

Polling interval: ~1 second.

---

# UI Views

The UI provides three primary views:

Runs List
Run Details
Live Logs

Runs List:

* table of pipeline runs
* auto refresh

Run Details:

* run status
* stage status
* progress indicators

Live Logs:

* streaming log output
* filters
* autoscroll

---

# Acceptance Criteria

The phase is complete when:

* UI can start a run
* UI can cancel a run
* UI can retry stage
* UI can retry run
* logs stream live
* progress updates live
* only one run executes at a time
* commands execute deterministically
