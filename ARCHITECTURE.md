
---

## `ARCHITECTURE.md`

```markdown
# System Architecture

DocMap is a pipeline system that processes SCP Wiki documents, extracts real geographic references, geocodes them, stores them in Postgres/PostGIS, and publishes analytics-ready datasets for BigQuery and Looker Studio.

The project is designed for AI-assisted implementation. Architecture must therefore remain explicit, modular, and stable.
This document is meant to close architectural ambiguity before implementation work starts.

---

# System Goal

The system maps documents to geographic locations mentioned in their text.

Important:

- the map represents documents, not SCP objects
- a single document may map to multiple locations
- Foundation facilities are not treated as real geolocations for the MVP map

---

# High-Level Architecture

Main flow:

SCP Wiki
↓
Crawler
↓
Document Storage
↓
LLM Extraction
↓
Geocoding
↓
Operational Database (Postgres + PostGIS)
↓
Analytics Layer
↓
BigQuery Export
↓
Looker Studio

---

# Core Layers

## 1. Source Layer

Source system:

- SCP Wiki pages such as `https://scp-wiki.wikidot.com/scp-173`

The source layer is external and not controlled by DocMap.

DocMap must treat source fetching as unreliable and rate-limited.

## 2. Snapshot Layer

This layer stores reproducible document states.

Each snapshot should preserve:

- raw HTML
- cleaned text
- PDF snapshot
- snapshot timestamp

This layer is the source of truth for extraction input.

## 3. Extraction Layer

This layer uses an LLM to identify geographic mentions from `clean_text`.

The output is structured JSON, validated before persistence.

This layer produces:

- extraction run metadata
- location mention records

## 4. Geocoding Layer

This layer resolves normalized location strings to real-world geodata using Nominatim.

This layer produces:

- geocoded locations
- document-location links

## 5. Analytics Layer

This layer reshapes operational data into BI-friendly structures.

It prepares:

- location-centric analytics
- document-centric analytics
- export-friendly tables

## 6. Publication Layer

This layer exports BI datasets to BigQuery.

Looker Studio reads from BigQuery, not from the operational Postgres database.

---

# Core Components and Responsibilities

## Crawler

Responsible for:

- URL generation/discovery
- page download
- HTML parsing
- clean text extraction
- PDF rendering
- snapshot persistence

## Extractor

Responsible for:

- prompt construction
- LLM invocation
- JSON validation
- extraction run persistence
- mention persistence

## Geocoder

Responsible for:

- resolving normalized locations
- caching geocode results
- creating geodata records
- linking mentions/documents to locations

## Pipeline Orchestrator

Responsible for:

- stage sequencing
- job selection
- incremental runs
- weekly runs
- partial reruns

## Analytics Exporter

Responsible for:

- building BI tables
- preparing export payloads
- pushing data to BigQuery

---

# Persistence Points

The architecture deliberately persists data at multiple boundaries.

These persistence points are important for reproducibility and reruns.

## Persistence Point 1: Document Snapshot

Stored after crawl.

Purpose:

- avoid repeated source fetching
- allow extraction reruns
- preserve exact source state

Stored data:

- raw_html
- clean_text
- pdf_path

## Persistence Point 2: Extraction Run

Stored after LLM extraction.

Purpose:

- compare models/prompts
- preserve extraction lineage
- audit failures

Stored data:

- snapshot reference
- model
- prompt version
- pipeline version
- timestamp

## Persistence Point 3: Location Mentions

Stored after extraction validation.

Purpose:

- preserve mention-level facts
- separate extraction from geocoding
- allow geocoding reruns

## Persistence Point 4: Geocoded Locations

Stored after geocoding.

Purpose:

- cache resolved places
- reuse geocoding results
- support spatial queries

## Persistence Point 5: BI Tables

Stored before export.

Purpose:

- isolate analytics from operational data
- simplify BigQuery export
- support repeatable publication

---

# Sequence of Operations

Default full processing sequence:

1. generate or discover SCP document URLs
2. download HTML pages
3. extract cleaned text
4. render/store PDF snapshots
5. persist document snapshots
6. select snapshots needing extraction
7. run LLM extraction
8. validate extraction JSON
9. persist extraction runs
10. persist location mentions
11. select unresolved normalized locations
12. geocode normalized locations
13. persist geocoded locations
14. create document-location links
15. rebuild BI tables
16. export BI tables to BigQuery

---

# Incremental Processing

The architecture must support incremental processing.

Incremental mode should:

- detect changed or newly discovered documents
- create new snapshots only when needed
- re-run extraction only on relevant snapshots
- geocode only unresolved or new normalized locations
- rebuild analytics and export after changes

This is necessary for weekly refreshes.

For the canonical SCP corpus:

- incremental refresh is driven by the full range `SCP-001` through `SCP-7999`
- missing canonical documents must be created automatically when first encountered
- the system must persist a document-level check marker even when content is unchanged
- changed documents create new snapshots, and only those new snapshots are extracted in normal incremental flow
- incremental crawl may still need to fetch documents to verify whether content changed; incrementality is defined by selective snapshot creation and downstream processing

Normalization architecture constraints:

- normalization remains an in-place transformation of `location_mentions.normalized_location`
- avoid adding normalization-specific state columns unless required to correct a proven logical defect
- when normalization rules materially change, the system must support corpus-wide renormalization
- invalid normalization outputs must not overwrite previously stored values
- repeated invalid normalization outputs during one run should be treated as a systemic failure and stop that normalization run

---

# Failure Handling

The system must support partial failure without full pipeline collapse.

## Source failures

If a page cannot be downloaded:

- log the failure
- retry according to retry policy
- continue processing other pages

If the source itself is broadly unavailable and requires operator intervention:

- stop the run
- preserve already committed progress
- emit a clear fatal log summary

## Extraction failures

If the LLM returns invalid JSON or fails:

- retry if appropriate
- log the failure
- preserve the snapshot
- continue with other snapshots

If the extraction service itself is unavailable and requires operator intervention:

- stop the run
- preserve already committed progress
- emit a clear fatal log summary

## Geocoding failures

If a place cannot be resolved:

- log the unresolved location
- continue with other locations

If geocoding returns an invalid payload or a non-retryable item-level error:

- log the detailed failure
- skip the item
- continue with other locations

If the geocoding service itself is unavailable and requires operator intervention:

- stop the run
- preserve already committed progress
- emit a clear fatal log summary

## Export failures

If BigQuery export fails:

- keep BI tables intact
- allow export retry without repeating crawl/extract/geocode

Export consistency rule:

- the export stage is considered atomic at the stage level
- if one BI table export fails, stop the export stage and mark the run failed
- do not continue with a partial mixed export state across BI tables

---

# Reprocessing Strategy

The architecture explicitly supports reruns.

Allowed reruns:

- crawl rerun for specific documents
- extraction rerun for existing snapshots
- geocoding rerun for unresolved mentions
- analytics rebuild without re-extraction
- export rerun without analytics rebuild

This is a core design requirement.

---

# Service Boundaries

Each service owns a narrow write surface.

- crawler writes snapshots
- extractor writes runs and mentions
- geocoder writes geolocations and links
- analytics exporter writes BI tables
- pipeline orchestrates, but does not own domain data

This boundary must not be violated without explicit architectural change.

---

# Weekly Update Flow

The default scheduled job is weekly.

Weekly update should execute the following logical sequence:

1. discover changed or new SCP pages
2. crawl changed/new pages
3. create snapshots for changed content
4. run extraction on new snapshots
5. geocode unresolved/new normalized locations
6. rebuild BI tables
7. export BI tables to BigQuery
8. publish completion status/logs

The weekly update must be incremental, not a mandatory full recrawl of the entire corpus.
The weekly target set is the full canonical SCP range, even when many documents are already known locally.

Pipeline modes must be explicit:

- `single-document` for one explicitly requested URL
- `incremental` for scheduled/default change-detection refresh
- `full` for a deliberate full pass over the canonical corpus

The first implementation does not require resumable run-state or checkpointing.

---

# MVP Deployment Model

All services should run in Docker.

Minimum expected runtime components:

- postgres/postgis
- pipeline service
- extractor service
- optional local nominatim later

In the MVP, some logical services may be implemented in one Python application, but the architectural boundaries described here must still remain explicit in code structure.

---

# Architectural Constraints

The implementation must preserve these constraints:

1. document snapshots are immutable historical records
2. extraction is separate from geocoding
3. operational tables are separate from BI tables
4. Looker reads from BigQuery, not from Postgres
5. one document may have many location links
6. Foundation facilities are not geocoded as real locations in MVP
7. Fatal infrastructure failures stop the run after preserving already committed progress
8. External dependency outages that require operator intervention stop the run rather than degrading silently

# SCP Wiki Parsing Constraints

SCP Wiki pages are built on the Wikidot platform.

Wikidot uses custom markup and dynamic page elements that may not be visible in the raw HTML or may appear multiple times.

The crawler must account for these platform-specific behaviors.

Failure to handle these correctly can significantly degrade LLM extraction quality.

---

# Wikidot Markup

SCP pages often contain Wikidot markup constructs.

Examples include:

- collapsible blocks
- hidden blocks
- tab views
- rating panels
- navigation elements
- metadata containers

Example constructs:


[[collapsible]]
[[/collapsible]]

[[tabview]]
[[tab]]
[[/tab]]
[[/tabview]]


These elements may hide content that is still part of the document narrative.

The crawler must ensure that **all narrative text is extracted**, even if it appears inside collapsible elements.

---

# Hidden Content Blocks

Some SCP pages include sections hidden by default in the browser UI.

These may contain:

- recovery logs
- experiment logs
- incident reports
- addenda

These sections are frequently implemented using collapsible Wikidot blocks.

Example:


[[collapsible show="Experiment Log"]]
content...
[[/collapsible]]


Even though these blocks appear hidden in the browser, **their contents must be included in the extracted text**.

The crawler must not discard them.

---

# Non-Content Elements

Many HTML elements on SCP Wiki pages are not part of the article content.

Examples:

- sidebar navigation
- rating module
- page tags
- edit links
- footer metadata

These elements must be removed from `clean_text`.

The crawler should extract only the **main article body**.

---

# Recommended Extraction Strategy

The crawler should:

1. Download the full HTML page.
2. Identify the main article container.
3. Remove navigation, footer, and metadata blocks.
4. Flatten Wikidot markup structures.
5. Extract clean readable text.

The goal is to produce `clean_text` suitable for LLM processing.

For the current hardening phase:

- improve the existing heuristics rather than redesigning the crawler around a full browser stack
- limit processing to content present in the fetched page
- do not require a canonical fixture set of SCP pages yet
- if extraction quality is questionable, log a warning and continue so that real corpus behavior can be observed before tightening rules further

---

# Text Quality Requirement

The extracted `clean_text` should:

- preserve narrative structure
- include experiment logs and addenda
- remove UI elements
- avoid markup artifacts

If the crawler extracts incomplete text, the LLM extraction stage will miss geographic references.

---

# PDF Snapshot Rendering

When generating the PDF snapshot of the page:

- ensure collapsible blocks are expanded
- ensure hidden sections are visible
- ensure the full narrative content is rendered

The PDF should represent the full readable article.

Implementation note for the current phase:

- only apply block-expansion behavior if it is simple to achieve with the chosen renderer
- otherwise prefer the simpler rendering path and revisit this later

---

# Common Crawler Failure Modes

The crawler must avoid these mistakes:

1. Extracting only the visible page summary.
2. Dropping collapsible sections.
3. Including navigation UI elements in the text.
4. Sending raw HTML to the LLM without cleaning.
5. Losing addenda sections containing important narrative context.

Any of these failures can significantly degrade the geographic extraction stage.

---

# Validation Recommendation

Crawler implementations should verify that extracted text length is reasonable.

Example heuristic:


clean_text length > 2000 characters


Very short outputs likely indicate that content extraction failed.

Such cases should be logged and retried.
