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

---

# Incremental Processing

The system must support incremental processing.

Examples:


re-run extraction on existing snapshots
re-run geocoding on unresolved locations
rebuild BI tables without crawling
retry BigQuery export


These capabilities are part of the architecture.

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


---

# Testing Expectations

Tests must exist for:


crawler
extractor JSON validation
geocoder responses
database queries


Tests must be placed in:


tests/


---

# Definition of Done

A development phase is complete when:

1. All tasks in the phase file are implemented.
2. Code builds successfully.
3. Docker services start.
4. Basic functionality works.
5. Tests pass.

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
