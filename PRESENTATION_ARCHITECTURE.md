# PRESENTATION_EXECUTION_RULES.md

This document defines strict execution rules for implementing the presentation layer.

The agent must follow these rules exactly.

The presentation layer is an **independent read-only visualization service**.

It consumes BI projections and exposes an interactive map-based interface.

The agent must not redesign the architecture.

---

# Authoritative Documents

Before writing any code the agent MUST read these documents in this order:

1. EXECUTION_SPEC.md
2. ARCHITECTURE.md
3. DATA_MODEL.md
4. SERVICES.md
5. PIPELINE.md
6. PRESENTATION_ARCHITECTURE.md
7. PRESENTATION_DATA_CONTRACT.md
8. PRESENTATION_UX_SPEC.md
9. PRESENTATION_API_SPEC.md
10. PRESENTATION_IMPLEMENTATION_PLAN.md
11. TASKS/phase11_presentation_layer.md

These documents define the architecture.

If conflicts appear, the order above defines priority.

---

# Architectural Role

The presentation layer:

reads BI tables  
exposes a read-only API  
renders the spatial UI

It does NOT:

run pipeline logic  
modify operational tables  
modify BI tables  
perform extraction or geocoding  

---

# UI Stack (Authoritative)

The presentation UI must use the following stack:

React  
Vite  
TypeScript  
MapLibre GL JS  
deck.gl  

This stack applies to the dedicated presentation frontend application.

The presentation frontend is separate from the control plane frontend and must be built and deployed independently as part of the presentation service container.

It must not replace the frontend with another framework.

Do not introduce alternative frameworks.

Do not replace the existing UI stack with:

Next.js  
Angular  
Vue  
Svelte  

unless explicitly instructed by the user.

---

# Frontend Module Layout

The presentation layer must be implemented as a separate frontend application.

It must NOT be merged into the control plane UI.

Recommended repository structure:

- `services/presentation/frontend/`
- `services/presentation/backend/`

Recommended frontend structure inside `services/presentation/frontend/src/`:

- `components/`
- `map/`
- `api/`
- `state/`
- `views/`

The presentation frontend may reuse shared patterns or utility code only if explicitly extracted into a neutral shared module.

It must not depend directly on control plane UI internals.

The agent must not replace or restructure the control plane UI while implementing the presentation layer.


# Frontend Replacement Prohibition

The agent must NOT replace the entire frontend architecture.

Specifically forbidden actions:

removing the existing `ui/` application  
replacing Vite with a different bundler  
introducing server-rendered frameworks  

The presentation layer must extend the existing UI structure.

---

# Geometry Rules

MVP supports **point geometries only**.

Allowed fields:

latitude  
longitude  

The agent must NOT implement:

polygons  
multi-polygons  
uncertainty radii  

These features may appear later but are not part of this phase.

---

# Search Rules

Search is **not part of MVP**.

The agent must NOT implement:

full-text search  
document search  
entity search  

unless explicitly instructed by the user.

Spatial navigation is the only discovery mechanism.

---

# SQL Portability Rules

All queries must be portable.

The agent must write SQL compatible with:

PostgreSQL  
BigQuery  
DuckDB  

Avoid:

database-specific extensions  
PostGIS-only features in API queries  

Coordinates must be returned as:

latitude  
longitude

not geometry blobs.

---

# BI Table Access

The presentation layer reads only:

bi_documents  
bi_locations  
bi_document_locations  
bi_location_hierarchy  

The agent must not write to these tables.

All BI tables are considered **immutable inputs**.

---

# Hierarchy Logic

Location hierarchy must support fallback:

city → region → country

Hierarchy information comes from:

bi_location_hierarchy

The agent must not compute hierarchy heuristically in the frontend.

Hierarchy resolution must occur in the API layer.

---

# Deterministic Behavior

The presentation layer must remain deterministic.

Given identical BI tables:

API responses must remain identical.

The agent must not introduce:

random ordering  
non-deterministic queries  
time-dependent logic  

---

# Performance Targets

The implementation must support at least:

5000 locations  
50000 document-location links  
50000 documents  

Hover interaction must remain under:

100 ms latency.

---

# UX Interaction Rules

The UI must implement two states:

hover  
pinned selection  

Behavior:

hover → preview documents  
click → pin selection  
Esc → reset  
click empty map → reset  

Document cards must:

display preview text  
open source document in new browser tab.

---

# Forbidden Architecture Changes

The agent must not introduce:

message brokers  
task queues  
background workers  
microservice splits  
data mutation pipelines  

The presentation layer is a **single read-only service**.

---

# Development Strategy

The agent must implement in this order:

1. BI schema adjustments
2. presentation API
3. UI shell
4. map rendering
5. hover/pin logic
6. document cards
7. map-to-panel synchronization
8. tests
9. documentation updates

---

# Success Criteria

The implementation is considered complete when:

the UI renders map locations  
hover shows documents  
click pins selection  
document cards display preview text  
links open SCP source pages  
API reads BI tables only  
no writes occur in the presentation service