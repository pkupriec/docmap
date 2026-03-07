# Service Contracts

This file defines service boundaries and write ownership.

## Services

1. crawler
2. extractor
3. geocoder
4. pipeline (orchestrator)
5. analytics exporter

Services may share one runtime in MVP, but boundaries stay strict in code.

## 1) Crawler

Responsibilities:
- discover/generate target URLs
- download page HTML
- extract `clean_text`
- generate PDF
- persist snapshots

Allowed writes:
- `scp_objects`
- `documents`
- `document_snapshots`

Forbidden writes:
- `extraction_runs`
- `location_mentions`
- `geo_locations`
- `document_locations`
- `bi_*`

Idempotency:
- do not create new snapshot for unchanged document unless explicitly requested

Retry/rate limit:
- 3 retries with exponential backoff
- minimum 1 request/second with jitter

## 2) Extractor

Responsibilities:
- read snapshot text
- call LLM
- validate response JSON
- persist run and mentions

Allowed writes:
- `extraction_runs`
- `location_mentions`

Forbidden writes:
- `geo_locations`
- `document_locations`
- `bi_*`

Validation minimum:
- valid JSON
- top-level `locations` array
- all required fields present
- numeric `confidence`

## 3) Geocoder

Responsibilities:
- resolve normalized locations
- cache geocode results
- persist geo rows
- link documents to locations

Allowed writes:
- `geo_locations`
- `document_locations`

Reads:
- `location_mentions`
- `extraction_runs`
- `documents`
- `document_snapshots`

Failure behavior:
- unresolved locations are logged and skipped

## 4) Pipeline (Orchestrator)

Responsibilities:
- sequence: crawl -> extract -> geocode -> analytics -> export
- choose processing scope (full, incremental, single-document)
- coordinate stage reruns

Write behavior:
- should not write domain tables owned by other services
- may write orchestration metadata if a job table is introduced later

## 5) Analytics Exporter

Responsibilities:
- build BI tables in Postgres
- export BI tables to BigQuery

Allowed writes:
- `bi_documents`
- `bi_locations`
- `bi_document_locations`

Forbidden writes:
- crawler/extractor/geocoder operational tables

## Cross-Service Rules

Ownership:
- each table has one owning writer service

Default sequence:
1. crawler
2. extractor
3. geocoder
4. analytics exporter

Reprocessing support:
- rerun extraction without recrawl
- rerun geocoding without re-extraction
- rerun export without analytics rebuild

Determinism:
- explicit inputs
- validated outputs
- structured logs
- no hidden side effects
