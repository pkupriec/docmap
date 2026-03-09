# Project Overview

## Mission

Build a reproducible pipeline that maps SCP documents to real-world locations referenced in text.

## Implemented Scope

- `implemented`: document crawl from SCP Wiki canonical URLs (`scp-001`..`scp-7999`)
- `implemented`: immutable-like snapshot history (`document_snapshots`) with `raw_html`, `clean_text`, `pdf_blob`
- `implemented`: LLM extraction via Ollama endpoint (`services/extractor/ollama_client.py`)
- `implemented`: geocoding via Nominatim + cache in `geo_locations`
- `implemented`: BI table rebuild in Postgres (`bi_*`)
- `implemented`: BigQuery export (full + incremental merge modes)
- `implemented`: control plane API + UI + SSE monitoring
- `implemented`: stage retry and stage resume controls

## Partially Implemented Scope

- `partial`: scheduler module exists but is not launched from `main.py`
- `partial`: production-grade auth/multi-tenant controls are absent by design
- `partial`: BigQuery setup/permissions are external and must be provided by operator

## Planned Scope

- `planned`: hardened publication playbook for downstream BI consumers (for example Looker)
- `planned`: deeper platform hardening (auth, queue UX, policy controls)

## Runtime Model

- Single Python API runtime (`uvicorn main:app`)
- One orchestrator thread polls and executes control commands
- Postgres/PostGIS as operational store and control-plane metadata store
- React/Vite operator UI as separate container in dev compose

## Constraints

- Single active run policy (`pending|running|cancelling` only one run at a time)
- Stage sequence for `full_pipeline`: `crawl -> extract -> geocode -> analytics -> export`
- Control API enqueues commands; only orchestrator mutates run/stage state
