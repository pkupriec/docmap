# Project Overview

## Mission

DocMap maps SCP documents to real-world locations referenced in text, with deterministic pipeline execution and operator observability.

## Current Implementation Status

Implemented:
- crawler, extractor, geocoder, analytics, export pipeline
- control API + orchestrator + operator UI
- presentation backend/frontend as separate read-only runtime
- canonical geo dictionary tables and refresh flow
- deterministic ambiguous-alias resolver for canonical matching
- stage retry and stage resume controls

Partially implemented:
- scheduler module exists but is not auto-started from `main.py`
- production authn/authz and deployment hardening are intentionally not part of current local stack
- BigQuery export requires operator-provided credentials and project settings

Planned:
- stronger production operations playbooks
- continued map/presentation quality improvements

## Runtime Topology

- Control runtime entrypoint: `main.py`
- Presentation runtime entrypoint: `main_presentation.py`
- Local stack: `infra/docker-compose.yml`
- Data stores: Postgres/PostGIS + optional BigQuery export

## Core Constraints

- One active pipeline run at a time (`pending|running|cancelling`).
- Stage order for full runs: `crawl -> extract -> geocode -> analytics -> export`.
- API enqueues commands; orchestrator applies mutations.
- Presentation is read-only and must not write operational or BI tables.