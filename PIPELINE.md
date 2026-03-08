# Processing Pipeline

This document defines the execution model for DocMap.
Its purpose is to make pipeline behavior explicit enough that the implementation agent mainly decides implementation details, not pipeline architecture.

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
- stop the run if the extraction service itself is unavailable and requires operator intervention

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
- retry transient transport failures up to 3 attempts with exponential backoff
- invalid geocoder payloads and non-retryable item errors are logged and skipped
- stop the run if the geocoding service itself is unavailable and requires operator intervention

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
- retry export per table up to 2 attempts with exponential backoff
- export must be consistent across all BI tables; if one table export fails, the export stage fails rather than continuing with a partial mixed export state

## Weekly Incremental Flow

Default schedule (see `TASKS/phase8_scheduler.md`):
1. discover targets
2. crawl + snapshot (changed/new only)
3. extract new snapshots
4. geocode unresolved/new normalized locations
5. rebuild BI tables
6. export to BigQuery

For the canonical SCP corpus, weekly incremental refresh traverses the full range `SCP-001` through `SCP-7999`.
Implementation may execute this in one pass or in simpler deterministic batches.

## Partial Rerun Requirements

The pipeline must support:
- crawl-only rerun
- extraction-only rerun on existing snapshots
- geocode-only rerun for unresolved values
- analytics-only rebuild
- export-only retry

Incremental refresh rules:
- revisit canonical documents even when they already exist in `documents`
- create missing canonical documents automatically when first encountered
- record document check activity even when content is unchanged
- only newly created snapshots are extracted during normal incremental runs
- incremental crawl may still fetch canonical documents to detect change; incrementality applies to downstream persistence and reprocessing, not to skipping verification entirely

Pipeline modes:
- `single-document`: process one explicitly requested document
- `incremental`: scheduled/default refresh over the canonical corpus with change detection
- `full`: full pass over the canonical corpus `SCP-001` through `SCP-7999`

The first implementation does not require resumable/checkpointed run state.

Normalization rules:
- normalization updates `location_mentions.normalized_location` in place
- schema should not gain dedicated normalization-state fields unless they are strictly required to fix a real logical defect
- when normalization rules change, the system must support renormalizing the full relevant corpus
- invalid normalization outcomes should be logged while preserving the previous value
- repeated invalid normalization outcomes in one run should stop the process as a likely systemic fault

Crawler quality rules for the current phase:
- improve text extraction heuristics incrementally rather than introducing a heavier browser-driven crawler
- operate only on content present in the fetched page
- if extracted text quality appears weak, log a warning and continue
- additional hard quality gates can be introduced later after real processed data is available

## Observability

All stages must emit structured logs with at least:
- timestamp
- service
- stage
- target
- status
- error (when present)
- run_id

Each stage and the overall pipeline must also emit a completion summary with:
- run_id
- stage
- processed
- succeeded
- failed
- skipped
- duration_seconds

## Constraints

- Extraction consumes `clean_text`, never raw HTML.
- Geocoding consumes `normalized_location`, never raw mention text.
- Snapshots are immutable.
- BI tables are derived and rebuildable.
- Export failures never force recrawl or re-extraction.
- Fatal infrastructure failures stop the run after preserving already committed progress.
- External dependency outages that require operator intervention stop the run rather than degrading silently.


## Command Processing

Pipeline execution is controlled through pipeline_commands.

Commands are written by the control API.

The orchestrator polls commands and applies them.

Commands are processed:

* sequentially
* in id order
* with row locking

Only one command modifying a run may execute at a time.

---

## Concurrency Model

Only one pipeline run may be active at any time.

Active statuses:

pending
running
cancelling

If a new start_run command arrives while a run is active:

the active run enters cancelling
after cancellation a new run starts.

---

## Retry Semantics

retry_run:

creates a new run.

retry_stage:

resets the stage and downstream stages.

If run is active:

cancel first, then restart.
