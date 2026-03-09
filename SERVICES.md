# Service Boundaries

This document is authoritative for module ownership and write boundaries.

## Ownership Matrix

- `crawler` (`implemented`): `scp_objects`, `documents`, `document_snapshots`
- `extractor` (`implemented`): `extraction_runs`, `location_mentions`
- `geocoder` (`implemented`): `geo_locations`, `document_locations`
- `analytics` (`implemented`): `bi_documents`, `bi_locations`, `bi_document_locations`
- `control plane` (`implemented`): `pipeline_runs`, `pipeline_stage_runs`, `pipeline_progress`, `pipeline_logs`, `pipeline_commands`

## 1) Crawler

Files: `services/crawler/*`

Responsibilities (`implemented`):
- canonical URL generation
- HTML fetch with retry/backoff and throttling
- clean text extraction
- PDF rendering to `pdf_blob`
- snapshot create-if-changed
- PDF backfill if snapshot exists but PDF missing

Notable limits:
- `partial`: content extraction heuristics are rule-based and can miss edge cases

## 2) Extractor

Files: `services/extractor/*`

Responsibilities (`implemented`):
- build prompt from snapshot clean text
- call Ollama generation endpoint
- parse and validate JSON response
- persist extraction run + mentions

Behavior:
- retries malformed/transient failures
- supports callback + stop boundary control

## 3) Geocoder

Files: `services/geocoder/*`

Responsibilities (`implemented`):
- normalize mentions (in-place updates)
- geocode unresolved mentions via Nominatim
- cache by normalized name
- create `document_locations` links

Behavior:
- unresolved/invalid items are logged and skipped
- supports callback + stop boundary control

## 4) Analytics

Files: `services/analytics/service.py`

Responsibilities (`implemented`):
- truncate/rebuild BI tables from operational data
- optional step callback with `start_index` support

## 5) BigQuery Export

Files: `services/analytics/bigquery_exporter.py`

Responsibilities (`implemented`):
- dataset ensure
- table export in `full` or `incremental` mode
- retry per table

Notable limits:
- `partial`: requires external credentials/permissions; no in-app secret management

## 6) Control Plane

Files: `services/control/*`

Responsibilities (`implemented`):
- API command enqueueing
- command polling/execution
- run/stage state transitions
- logs/progress emission
- SSE event stream

Notable limits:
- `partial`: no authentication/authorization layer
- `partial`: no dedicated external queue/broker
