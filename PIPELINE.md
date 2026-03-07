# Processing Pipeline

This document defines the execution model for DocMap.

## Goal

Transform SCP Wiki pages into analytics-ready, geocoded document-location mappings for BigQuery and Looker Studio.

## End-to-End Stages

1. Target discovery
2. Crawl and snapshot
3. Extraction
4. Geocoding
5. Analytics rebuild
6. BigQuery export

## Stage Contracts

### 1) Target discovery

Inputs:
- configured SCP range
- manual URL(s)
- incremental schedule

Output:
- list of document URLs to process

Failure behavior:
- unresolved targets are logged and skipped

### 2) Crawl and snapshot

Inputs:
- document URL

Actions:
- download HTML
- derive `clean_text`
- render PDF
- persist snapshot artifacts

Writes:
- `scp_objects`
- `documents`
- `document_snapshots`

Incremental rule:
- compute `sha256(clean_text)` for current crawl
- compare to latest snapshot hash derived from latest stored `clean_text`
- insert new snapshot only on first-seen doc, changed hash, or explicit resnapshot

Failure behavior:
- document-level retry with backoff
- skip failed documents and continue batch

### 3) Extraction

Inputs:
- `document_snapshots.clean_text`
- extraction model and prompt version

Output JSON contract:

```json
{
  "locations": [
    {
      "mention_text": "...",
      "normalized_location": "...",
      "precision": "city|admin_region|country|coordinates|unknown",
      "relation_type": "unspecified",
      "confidence": 0.0,
      "evidence_quote": "..."
    }
  ]
}
```

Writes:
- `extraction_runs`
- `location_mentions`

Failure behavior:
- retry malformed JSON and transient transport errors
- preserve snapshot for later rerun

### 4) Geocoding

Inputs:
- unresolved `normalized_location` values from `location_mentions`

Actions:
- cache lookup by `normalized_location`
- Nominatim lookup when cache miss
- normalize response to canonical geodata fields

Writes:
- `geo_locations`
- `document_locations`

Failure behavior:
- unresolved names are logged
- continue with remaining locations

### 5) Analytics rebuild

Inputs:
- operational tables

Writes:
- `bi_documents`
- `bi_locations`
- `bi_document_locations`

Failure behavior:
- do not mutate operational tables
- rerunnable independently

### 6) BigQuery export

Inputs:
- BI tables in Postgres

Outputs:
- BigQuery tables:
  - `bi_documents`
  - `bi_locations`
  - `bi_document_locations`

Modes:
- full (`WRITE_TRUNCATE`)
- incremental (staging + `MERGE`)

Failure behavior:
- keep local BI tables intact
- allow export-only retry

## Weekly Incremental Flow

Default schedule (see `TASKS/phase8_scheduler.md`):
1. discover targets
2. crawl + snapshot (changed/new only)
3. extract new snapshots
4. geocode unresolved/new normalized locations
5. rebuild BI tables
6. export to BigQuery

## Partial Rerun Requirements

The pipeline must support:
- crawl-only rerun
- extraction-only rerun on existing snapshots
- geocode-only rerun for unresolved values
- analytics-only rebuild
- export-only retry

## Observability

All stages must emit structured logs with at least:
- timestamp
- service
- stage
- target
- status
- error (when present)

## Constraints

- Extraction consumes `clean_text`, never raw HTML.
- Geocoding consumes `normalized_location`, never raw mention text.
- Snapshots are immutable.
- BI tables are derived and rebuildable.
- Export failures never force recrawl or re-extraction.
