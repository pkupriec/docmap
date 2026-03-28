# Phase 9 - Pipeline Hardening

Goal: harden runtime behavior after the initial MVP implementation.

Status:
- Draft
- Architectural decisions for this phase should be recorded here before implementation.
- The implementation agent should solve "how to implement" and should not reopen already documented architectural decisions.

## Scope

1. Pipeline-wide error handling and failure isolation.
2. Deterministic incremental document refresh for existing corpus pages.
3. Proper full-pipeline and incremental discovery/orchestration modes.
4. Incremental-safe normalization flow.
5. Stronger SCP Wiki/Wikidot content extraction.
6. Agent workflow updates for test policy.

## Initial Workstreams

### 9.1 Error handling and resilience

- isolate failures per document, snapshot, mention, and export table
- define retryable vs non-retryable errors
- add stage summaries to logs
- keep pipeline progressing on partial failures where architecture allows

Decisions:
- fatal infrastructure/orchestration failures stop the whole run
- external dependency outage requiring intervention stops the run after preserving already committed progress
- retry budgets:
  - crawler: 3 attempts with exponential backoff
  - extractor/Ollama: 3 attempts with exponential backoff
  - geocoder/Nominatim: 3 attempts with exponential backoff
  - BigQuery export: 2 attempts per table
- geocoding failures are logged with detail and skipped; no dedicated database status is required at this stage
- every stage and full pipeline run must emit a summary with:
  - `run_id`
  - `stage`
  - `processed`
  - `succeeded`
  - `failed`
  - `skipped`
  - `duration_seconds`
- export must remain consistent; if one BI table export fails, the export stage is considered failed and should stop rather than continue with a partial mixed export state

### 9.2 Incremental refresh of documents

- revisit existing documents regularly
- detect changed content via `sha256(clean_text)`
- create new snapshots only for changed/new documents
- skip unchanged documents without re-extraction

Decisions:
- weekly incremental refresh traverses the full canonical range `SCP-001` through `SCP-7999`
- batching is allowed, but the implementation should prefer the simplest deterministic approach
- missing canonical documents must be created automatically when first encountered
- the system must persist a document-level "last checked" marker even when content is unchanged
- only newly created snapshots are extracted during normal incremental runs

### 9.3 Pipeline modes

- define real `single-document`, `incremental`, and `full` modes
- ensure scheduler uses an actual incremental refresh mode
- prepare orchestration surfaces for a future UI

Decisions:
- `full` means a full pass across the entire canonical corpus `SCP-001` through `SCP-7999`
- no separate `manual-batch` mode is required at this stage
- no resumable/checkpointed run state is required in the first implementation
- scheduler continues to run only the `incremental` mode
- incremental crawl still revisits the canonical corpus; its incremental behavior is that unchanged documents do not create new snapshots and do not trigger downstream reprocessing

### 9.4 Normalization hardening

- process only mentions that still require normalization
- avoid re-reading the same early rows forever
- make normalization progress monotonic across large tables

Decisions:
- do not add new normalization state columns unless strictly required to fix logical defects
- normalization remains an in-place update of `location_mentions.normalized_location`
- if normalization rules change, the system must support renormalizing the full relevant corpus
- if a normalization attempt produces an empty or obviously invalid value, log the failure and keep the previous value
- if such normalization failures repeat many times in one run (threshold to be implemented in the 3-5 range), stop the process because the rules or input assumptions are likely broken
- no normalization versioning model is required at this stage

### 9.5 SCP Wiki parsing hardening

- improve extraction of article text from Wikidot pages
- preserve addenda, logs, and collapsible narrative blocks
- remove UI noise more reliably
- validate PDF rendering completeness

Decisions:
- improve the current heuristics rather than introducing a heavy parser redesign
- do not require a fixed set of canonical SCP page fixtures at this stage
- limit parsing/rendering to content available on the fetched page; do not add browser automation or JS-driven expansion now
- for PDF rendering, do not overcomplicate the implementation; expand blocks only if it is trivial via renderer parameters, otherwise keep the simpler path
- do not define additional hard quality gates for `clean_text` yet beyond current heuristics and logging
- if the crawler cannot confidently extract strong text quality, log a warning and continue rather than blocking the pipeline

### 9.6 Agent guidance updates

- relax the "tests always required" rule
- let the implementation agent choose test depth based on risk
- require explicit note when changes ship without new tests

Decisions:
- preserve the current practical approach demonstrated in the repository
- tests are primarily a self-check mechanism for the implementation agent
- the agent chooses whether to add or run unit tests, integration tests, or no new tests based on change risk and available verification paths
- tests are not a mandatory artifact for every change, but verification remains mandatory
- when no new tests are added, the agent should still state how the change was checked or why additional tests were unnecessary
- if an existing test covers logic that changes, that test must be updated to match the new intended behavior

## Acceptance Direction

This phase is complete when:

1. Runtime modes are explicit and usable.
2. Incremental refresh revisits existing documents deterministically.
3. Partial failures are isolated and visible in logs.
4. Normalization and geocoding make forward progress on large datasets.
5. Crawler output quality is robust enough for real SCP Wiki pages.
6. Agent instructions reflect the desired test policy.

## Current Instructions For Implementation Agent

When implementing 9.1:

1. Preserve already committed progress when a fatal external dependency outage occurs, then fail the run clearly.
2. Distinguish retryable transport/transient failures from non-retryable data/contract failures.
3. Stop the run on:
   - database connectivity/configuration failures
   - inability to read/write required pipeline tables
   - external dependency outages that require operator intervention
   - inconsistent BigQuery export where one target table cannot be exported
4. Continue item-level processing only for isolated record failures inside an otherwise healthy stage.
5. Emit end-of-stage and end-of-run summary logs using the required summary fields.

When implementing 9.2:

1. Drive weekly incremental refresh from the full canonical SCP range, not only from already-known rows in `documents`.
2. Keep the implementation deterministic, but prefer the simplest batching model.
3. Automatically create missing `documents` rows when a canonical SCP page is first encountered during refresh.
4. Add and maintain a document-level `last_checked_at` marker even when no new snapshot is created.
5. Ensure changed documents create a new immutable snapshot and only that new snapshot becomes eligible for extraction.

When implementing 9.3:

1. Define `run_full_pipeline()` as a full pass over the canonical SCP corpus, not merely over caller-supplied URLs.
2. Keep `run_incremental_pipeline()` as the scheduled/default refresh mode.
3. Do not introduce resumable run-state or manual-batch orchestration yet.
4. Make the crawl semantics explicit: incremental crawl still fetches documents to detect changes, but unchanged documents must not create new snapshots or trigger downstream work.

When implementing 9.4:

1. Fix normalization progress without adding new schema fields unless they are strictly necessary to correct a logical defect.
2. Keep normalization as an in-place update of `location_mentions.normalized_location`.
3. Support corpus-wide renormalization when normalization rules change.
4. If a normalization result is empty or obviously invalid, log it and preserve the previous value.
5. Abort the normalization process when repeated invalid-normalization outcomes indicate a systemic issue, using an implementation threshold in the 3-5 range.

When implementing 9.5:

1. Improve the current crawler heuristics rather than redesigning the crawler around browser automation or fixture-driven parsing.
2. Limit extraction to what is present in the fetched page content.
3. Keep PDF generation simple; only expand hidden/collapsible content if there is a low-complexity renderer option for it.
4. Use warnings and continuation when content quality looks weak instead of failing the run.

When implementing 9.6:

1. Treat tests primarily as a self-check mechanism for the implementation agent.
2. Choose verification depth based on risk: unit tests, integration tests, runtime validation, or another appropriate check.
3. Do not add tests mechanically when they do not materially improve confidence.
4. Update existing tests when they already cover the logic being changed.
5. Always report what verification was performed, and explicitly say when no new tests were added.
