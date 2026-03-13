# Project Overview

## Mission

Build a reproducible pipeline that maps SCP documents to real-world locations referenced in text.

## Implemented Scope

- `implemented`: document crawl from SCP Wiki canonical URLs (`scp-001`..`scp-7999`)
- `implemented`: immutable-like snapshot history (`document_snapshots`) with `raw_html`, `clean_text`, `pdf_blob`
- `implemented`: LLM extraction via Ollama endpoint (`services/extractor/ollama_client.py`)
  - model/tuning controls are env-configurable (`EXTRACTOR_MODEL`, `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_THINK_LEVEL`, `OLLAMA_NUM_PREDICT`)
  - extraction prompt includes stricter anti-hallucination and normalization guidance
- `implemented`: geocoding via Nominatim + cache in `geo_locations`
  - request pacing and 429 handling are built in for public Nominatim usage
  - per-mention commit semantics improve durability for long geocode runs
- `implemented`: BI table rebuild in Postgres (`bi_*`)
- `implemented`: BigQuery export (full + incremental merge modes)
- `implemented`: control plane API + UI + SSE monitoring
- `implemented`: stage retry and stage resume controls
- `implemented`: presentation layer API + dedicated map UI (`services/presentation/*`, container `presentation`)
  - `partial`: current mixed geometry is limited by low-coverage static assets and name-based matching

## Partially Implemented Scope

- `partial`: scheduler module exists but is not launched from `main.py`
- `partial`: production-grade auth/multi-tenant controls are absent by design
- `partial`: BigQuery setup/permissions are external and must be provided by operator

## Planned Scope

- `planned`: hardened publication playbook for downstream BI consumers (for example Looker)
- `planned`: deeper platform hardening (auth, queue UX, policy controls)
- `planned`: phase 13 real-geometry rendering for `admin_region`, `country`, `continent`, and `ocean`, without extending fallback beyond `city -> region -> country`

## Runtime Model

- Single Python API runtime (`uvicorn main:app`)
- One orchestrator thread polls and executes control commands
- Postgres/PostGIS as operational store and control-plane metadata store
- React/Vite operator UI as separate container in dev compose
- Separate presentation runtime (`main_presentation.py`) serving presentation API + built frontend

## Constraints

- Single active run policy (`pending|running|cancelling` only one run at a time)
- Stage sequence for `full_pipeline`: `crawl -> extract -> geocode -> analytics -> export`
- Control API enqueues commands; only orchestrator mutates run/stage state
