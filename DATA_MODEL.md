# Data Model

This document defines the relational data model for DocMap.

The purpose of the data model is to represent:

- SCP documents
- document snapshots
- LLM extraction results
- geographic locations
- document-to-location relationships
- BI datasets

The database uses:

PostgreSQL + PostGIS.

---

# Design Principles

The model follows these principles:

1. Source snapshots are immutable.
2. Extraction results are versioned.
3. Geocoding is separated from extraction.
4. Document-to-location mapping is explicit.
5. BI datasets are isolated from operational data.

---

# Entity Overview

Main entities:


SCP Object
↓
Document
↓
Document Snapshot
↓
Extraction Run
↓
Location Mention
↓
Geo Location
↓
Document Location


---

# SCP Objects

Represents canonical SCP identifiers.

Example:


SCP-173
SCP-096
SCP-3000


Table:


scp_objects


Fields:

| field | description |
|------|-------------|
id | UUID primary key |
canonical_number | SCP number (e.g. SCP-173) |

Constraints:


UNIQUE(canonical_number)


---

# Documents

Represents the canonical SCP Wiki page.

Example:


https://scp-wiki.wikidot.com/scp-173


Table:


documents


Fields:

| field | description |
|------|-------------|
id | UUID primary key |
scp_object_id | reference to SCP object |
url | canonical document URL |
title | page title |
created_at | first discovery timestamp |

Constraints:


UNIQUE(url)


Relationship:


scp_objects 1 → N documents


---

# Document Snapshots

Represents a specific version of the document content.

Snapshots allow:

- reproducibility
- extraction reruns
- historical comparison

Table:


document_snapshots


Fields:

| field | description |
|------|-------------|
id | UUID primary key |
document_id | document reference |
raw_html | original HTML |
clean_text | cleaned text for LLM |
pdf_path | path to PDF snapshot |
created_at | snapshot timestamp |

Relationship:


documents 1 → N document_snapshots


Snapshots are immutable.

---

# Extraction Runs

Represents one execution of the LLM extraction.

This allows comparing:

- models
- prompt versions
- pipeline versions

Table:


extraction_runs


Fields:

| field | description |
|------|-------------|
id | UUID primary key |
snapshot_id | document snapshot |
model | LLM model used |
prompt_version | prompt identifier |
pipeline_version | pipeline version |
created_at | extraction timestamp |

Relationship:


document_snapshots 1 → N extraction_runs


---

# Location Mentions

Represents geographic mentions detected by the LLM.

Example mention:


"near Kyoto"


Normalized form:


Kyoto, Japan


Table:


location_mentions


Fields:

| field | description |
|------|-------------|
id | UUID primary key |
run_id | extraction run reference |
mention_text | text span |
normalized_location | normalized place name |
precision | city / region / country |
relation_type | optional semantic relation |
confidence | model confidence |
evidence_quote | supporting quote |

Relationship:


extraction_runs 1 → N location_mentions


---

# Geo Locations

Represents resolved geographic coordinates.

Example:


Kyoto, Japan
35.0116
135.7681


Table:


geo_locations


Fields:

| field | description |
|------|-------------|
id | UUID primary key |
normalized_location | canonical location string |
country | country |
region | administrative region |
city | city |
latitude | latitude |
longitude | longitude |
precision | location precision |
geom | PostGIS geometry |

Constraints:


UNIQUE(normalized_location)


---

# Document Locations

Represents the mapping between documents and geocoded locations.

This allows:

- one document → many locations
- one location → many documents

Table:


document_locations


Fields:

| field | description |
|------|-------------|
id | UUID primary key |
document_id | document reference |
location_id | geolocation reference |
mention_id | source mention |

Relationship:


documents N ↔ N geo_locations


via `document_locations`.

---

# BI Tables

Operational tables should not be used directly by BI tools.

Instead, analytics tables are generated.

Examples:


bi_documents
bi_locations
bi_document_locations


These tables are exported to BigQuery.

Looker Studio reads from BigQuery only.

---

# Operational vs BI Layer

Operational tables:


scp_objects
documents
document_snapshots
extraction_runs
location_mentions
geo_locations
document_locations


BI tables:


bi_documents
bi_locations
bi_document_locations


BI tables are derived and may be rebuilt at any time.