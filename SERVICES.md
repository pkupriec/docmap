# Service Contracts

This file defines service boundaries and write ownership.

## Services

1. crawler
2. extractor
3. geocoder
4. pipeline (orchestrator)
5. analytics exporter

Services may share one runtime in MVP, but boundaries stay strict in code.
Architectural decisions documented here are intended to remove design ambiguity for the implementation agent.

## 1) Crawler

Responsibilities:
- discover/generate target URLs
- download page HTML
- extract `clean_text`
- generate PDF
- persist snapshots

Current hardening direction:
- improve parser heuristics incrementally
- avoid browser-automation complexity for now
- continue on weak text quality with warning logs rather than failing the batch

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
- still record that the document was checked during incremental refresh even when no snapshot is created

Retry/rate limit:
- 3 retries with exponential backoff
- minimum 1 request/second with jitter

Incremental refresh source:
- weekly incremental refresh traverses the full canonical range `SCP-001` through `SCP-7999`
- missing canonical documents must be created automatically when first encountered
- incremental crawl may still fetch already-known canonical documents to detect change

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
- transient transport failures retry up to 3 attempts with exponential backoff
- invalid payloads and non-retryable item errors are logged and skipped
- if the geocoding service itself is unavailable and requires operator intervention, the run stops after preserving already committed progress

Normalization support rules:
- normalization updates `location_mentions.normalized_location` in place
- avoid adding extra normalization-state columns unless required to fix a real logical defect
- support full renormalization when normalization rules change
- if normalization produces an invalid result, log it and preserve the prior value
- if invalid normalization outcomes repeat beyond a small threshold in one run, stop the normalization process

## 4) Pipeline (Orchestrator)

Responsibilities:
- sequence: crawl -> extract -> geocode -> analytics -> export
- choose processing scope (full, incremental, single-document)
- coordinate stage reruns

Write behavior:
- should not write domain tables owned by other services
- may write orchestration metadata if a job table is introduced later
- must emit stage-level and run-level summary logs with counts and duration

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

Failure behavior:
- retry export per table up to 2 attempts with exponential backoff
- keep BI tables intact on export failure
- stop export stage on first table failure to preserve cross-table consistency

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
