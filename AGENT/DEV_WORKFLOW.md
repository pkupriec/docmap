# Development Workflow

This repository is designed for AI-assisted development.

The AI coding agent is responsible for implementing the DocMap system following the architecture defined in this repository.

The agent must follow the workflow described below.

---

# Development Process

The agent must implement the system in phases.

Task phases are located in:

TASKS/

Files:

phase0_bootstrap.md
phase1_database.md
phase2_crawler.md
phase3_extraction.md
phase4_normalization.md
phase5_geocoding.md
phase6_analytics.md
phase7_bigquery.md
phase8_scheduler.md
phase9_pipeline_hardening.md

The agent must implement tasks sequentially.

---

# Task Execution Strategy

For each phase:

1. Read the task file.
2. Implement the tasks in logical order.
3. Commit changes incrementally.

The agent must avoid implementing multiple phases at once.
The agent should treat documented architectural decisions as pre-resolved and focus on implementation details.
The agent should regulate reasoning conservatively: low for mechanical changes, medium by default, high only for genuinely complex or risky implementation work.

---

# Commit Strategy

Commits must be small and descriptive.

Example commit messages:

feat: implement scp_objects table

feat: implement crawler HTML downloader

feat: add extraction service

fix: handle invalid JSON from LLM

---

# Code Organization

All services must be modular.

Services must be placed in:

services/

Example structure:

services/
    crawler/
    extractor/
    geocoder/
    pipeline/

Each service must be independent.

---

# Database Changes

Database schema must be stored in:

database/schema.sql

Schema updates must be made via migrations.

The agent must not change schema without updating documentation.

---

# Running the System

All services must run through Docker.

Use:

docker-compose

Location:

infra/docker-compose.yml

The agent must ensure services start correctly.

---

# Testing

Each service may include tests where they materially improve confidence.

Tests are primarily for agent self-check and may verify:

crawler downloads pages
LLM extraction returns valid JSON
geocoder returns coordinates
database queries work

When tests are written, they should be placed in:

tests/

The implementation agent should choose the verification method based on change risk.
This may include unit tests, integration tests, runtime validation, or manual reasoning from existing coverage.
If an existing test already covers the changed logic, the agent should update that test accordingly.

---

# Logging

All services must produce structured logs.

Logs must include:

timestamp
service name
operation
status

---

# Error Handling

Services must handle failures gracefully.

Examples:

crawler retry logic
LLM JSON validation
geocoder request failures

The pipeline must not crash due to single document failure.

---

# Documentation Updates

If the agent changes architecture or behavior, it must update:

ARCHITECTURE.md
DATA_MODEL.md
PIPELINE.md

---

# Definition of Done

A phase is complete when:

1. All tasks in the phase file are implemented.
2. The code builds successfully.
3. Docker services start correctly.
4. Basic functionality works.
5. Verification appropriate to the change has been performed.

Only after completing a phase should the agent proceed to the next phase.

---

# Important Constraints

The agent must follow the architecture defined in this repository.

The agent must not redesign the system without explicit approval.

All major architectural decisions are already documented.
The agent should not spend effort redesigning decisions that are already fixed in the docs.

## Finalization Step

Before considering a task complete, the agent must perform a documentation synchronization pass.

Required finalization sequence:
1. implement the change
2. verify the change
3. update affected documentation
4. check for stale statements in README, architecture, pipeline, data model, operations, and configuration docs
5. include documentation updates in the same change set unless the user explicitly asked not to

The agent must treat stale documentation as a defect.