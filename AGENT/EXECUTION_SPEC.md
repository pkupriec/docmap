# Agent Execution Specification

This document defines how the AI coding agent must execute development in this repository.

It connects:

- architecture
- service contracts
- pipeline
- development tasks

The purpose of this document is to prevent architectural drift and ensure deterministic implementation.

---

# Primary Goal

Implement the DocMap system.

DocMap extracts geographic locations from SCP Wiki documents and maps documents to those locations.

Important:

The system maps **documents**, not SCP objects.

A document may reference multiple geographic locations.

---

# System Pipeline

The final pipeline must follow this sequence:


SCP Wiki
↓
Crawler
↓
Document Snapshots
↓
LLM Extraction
↓
Location Mentions
↓
Geocoding
↓
Geo Locations
↓
Document-Location Mapping
↓
BI Tables
↓
BigQuery Export
↓
Looker Studio Map


The pipeline architecture is described in:


ARCHITECTURE.md
PIPELINE.md
SERVICES.md


The agent must read these files before implementing code.

---

# Service Architecture

The system consists of five logical services.


crawler
extractor
geocoder
pipeline
analytics exporter


Responsibilities are defined in:


SERVICES.md


The agent must not merge responsibilities across services.

Example:

Crawler must NOT call the LLM.

Extractor must NOT geocode locations.

---

# Database Ownership

Database schema is defined in:


database/schema.sql


Table ownership:

| service | tables it writes |
|-------|----------------|
crawler | scp_objects, documents, document_snapshots |
extractor | extraction_runs, location_mentions |
geocoder | geo_locations, document_locations |
analytics | bi_* tables |

Services must not write outside their domain tables.

---

# Development Strategy

Development is organized into phases located in:


TASKS/


Phases:


phase0_bootstrap
phase1_database
phase2_crawler
phase3_extraction
phase4_normalization
phase5_geocoding
phase6_analytics
phase7_bigquery
phase8_scheduler
phase9_pipeline_hardening


The agent must execute phases sequentially.

Do not skip phases.

---

# Implementation Rules

The agent must follow these rules:

1. Respect architecture boundaries.
2. Implement services modularly.
3. Keep files small and readable.
4. Use structured logging.
5. Handle errors gracefully.
6. Avoid breaking database contracts.
7. Treat documented architectural decisions as fixed unless the user explicitly reopens them.

Reasoning policy:

- use reasoning conservatively and adjust it to task complexity
- prefer `low` for small local or mechanical changes
- prefer `medium` by default for normal implementation work in this repository
- use `high` only for tasks with high coupling, tricky invariants, schema-impacting changes, orchestration logic, or high regression risk
- once the implementation path is clear, reduce reasoning level rather than keeping it unnecessarily high

---

# Code Layout

The expected project structure is:


services/
crawler/
extractor/
geocoder/
pipeline/
analytics/

database/
infra/
tests/


Each service must be implemented as a Python module.

Example:


services/crawler/downloader.py
services/extractor/llm_client.py
services/geocoder/nominatim_client.py


---

# Runtime Environment

The system runs in Docker.

Infrastructure is defined in:


infra/docker-compose.yml


Minimum services:


postgres (PostGIS)
application container


The application container executes Python services.

---

# LLM Extraction

LLM extraction must use the prompt defined in:


services/extractor/prompts/location_extraction_prompt.md


The agent must not modify the JSON output format unless explicitly instructed.

Expected JSON structure:


{
"locations": [
{
"mention_text": "...",
"normalized_location": "...",
"precision": "...",
"relation_type": "...",
"confidence": 0.0,
"evidence_quote": "..."
}
]
}


---

# Error Handling

Failures must not stop the entire pipeline.

Examples:

Crawler failure → skip document.

Extraction failure → retry or log.

Geocoding failure → mark unresolved.

Export failure → retry export only.

Exception:

- fatal infrastructure failures must stop the run after preserving already committed progress
- external dependency outages that require operator intervention must stop the run
- item-level failures inside an otherwise healthy stage should still be isolated and logged

---

# Incremental Processing

The system must support incremental processing.

Examples:


re-run extraction on existing snapshots
re-run geocoding on unresolved locations
rebuild BI tables without crawling
retry BigQuery export


These capabilities are part of the architecture.

Incremental corpus refresh contract:

- weekly incremental refresh uses the full canonical range `SCP-001` through `SCP-7999`
- missing canonical documents must be inserted automatically when first encountered
- the system must record document refresh checks even when content is unchanged
- only newly created snapshots are extracted during normal incremental runs
- incremental crawl may still fetch documents to determine whether they changed

Pipeline mode contract:

- `run_full_pipeline()` means a full pass over the canonical corpus
- scheduler continues to run only `incremental`
- no resumable/checkpointed run-state is required in the first implementation

Normalization contract:

- keep normalization as an in-place update of `location_mentions.normalized_location`
- do not add normalization-specific state/version columns unless strictly required to fix a real logical defect
- support full renormalization when normalization rules change
- invalid normalization results must be logged and must not overwrite the previous value
- repeated invalid normalization results in one run should stop the normalization process

Crawler hardening contract:

- prefer improving existing extraction heuristics over introducing browser automation
- operate only on content available in the fetched page
- do not require canonical crawler fixtures in the current phase
- when text quality looks weak, log a warning and continue

---

# Logging

All services must emit structured logs.

Minimum fields:


timestamp
service
operation
target
status
error
run_id

Required summary fields for each stage and full pipeline run:

processed
succeeded
failed
skipped
duration_seconds


---

# Testing Expectations

Tests should exist where they materially improve confidence, especially for:


crawler
extractor JSON validation
geocoder responses
database queries


When tests are written, they should be placed in:


tests/

Test policy:

- tests are primarily a self-check mechanism for the implementation agent
- the agent may choose unit tests, integration tests, or no new tests based on the risk and scope of the change
- verification is still required even when no new tests are added
- the agent should explicitly report what verification was performed
- if an existing test covers logic that is being changed, the agent should update that test to match the new intended behavior


---

# Definition of Done

A development phase is complete when:

1. All tasks in the phase file are implemented.
2. Code builds successfully.
3. Docker services start.
4. Basic functionality works.
5. Verification appropriate to the change has been performed; when tests are used, they pass.

Only then may the agent proceed to the next phase.

---

# Architectural Constraints

The agent must preserve the following invariants:

1. Document snapshots are immutable.
2. Extraction and geocoding are separate stages.
3. Operational tables are not used directly by BI.
4. Looker reads only from BigQuery.
5. One document may link to many locations.

These constraints define the core architecture of DocMap.

---

# Autonomous Readiness

Before autonomous implementation begins, the agent must verify:

- `AGENT/AUTONOMY_CHECKLIST.md`

If any checklist gate fails, the agent must patch specs first and only then continue phase execution.

Implementation stance:

- prefer deciding "how to implement" rather than "what to build" when the architecture and task files already answer the latter
- if the docs are explicit, implement them directly instead of re-deriving product or architecture choices


## Phase 10 — Control Plane Implementation

Agents implementing phase10_control_plane must:

1. Implement control API in the existing Python application.
2. Implement pipeline_commands command queue.
3. Implement orchestrator command polling loop.
4. Implement pipeline_logs logging.
5. Implement pipeline_progress updates.
6. Implement SSE endpoint.
7. Implement React UI.

Agents must not:

* introduce message brokers
* introduce multiple command workers
* introduce multiple concurrent runs
* introduce scheduling systems
* introduce authentication systems
