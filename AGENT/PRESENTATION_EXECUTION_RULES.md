# PRESENTATION_EXECUTION_RULES.md

This document defines strict execution rules for implementing the presentation layer.

The agent must follow these rules exactly.

The presentation layer is an independent read-only visualization service.

It consumes BI projections and exposes an interactive map-based interface.

The agent must not redesign the architecture.

---

# Authoritative Documents

Before writing any code the agent MUST read these documents in this order:

1. AGENT/EXECUTION_SPEC.md
2. ARCHITECTURE.md
3. DATA_MODEL.md
4. SERVICES.md
5. PIPELINE.md
6. PROJECT.md
7. docs/DOMAIN_CONTEXT.md
8. AGENT/ANTI_PATTERNS.md
9. AGENT/CODING_CONVENTIONS.md
10. AGENT/DEV_WORKFLOW.md
11. AGENT/AUTONOMY_CHECKLIST.md
12. PRESENTATION_ARCHITECTURE.md
13. PRESENTATION_DATA_CONTRACT.md
14. PRESENTATION_UX_SPEC.md
15. PRESENTATION_API_SPEC.md
16. PRESENTATION_IMPLEMENTATION_PLAN.md
17. TASKS/phase11_presentation_layer.md

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

# Deployment Boundary

The presentation layer must be deployable as a separate container.

The container must include the presentation backend and the presentation frontend required for this service.

The presentation layer must not be bundled into the control plane container.

Shared repository does not imply shared runtime artifact.


# UI Stack (Authoritative)

The presentation UI must use the following stack:

React  
Vite  
TypeScript  
MapLibre GL JS  
deck.gl  

This stack applies to a dedicated presentation frontend application.

Do not introduce alternative frameworks unless explicitly instructed by the user.

---

# Frontend Replacement Prohibition

The agent must NOT merge the presentation frontend into the control plane frontend.

Specifically forbidden actions:

placing presentation UI files inside the control plane UI application  
restructuring the control plane UI in order to host presentation features  
removing or replacing the control plane UI application  
replacing Vite with a different bundler for the presentation frontend without explicit instruction  
introducing server-rendered frameworks without explicit instruction  

The presentation layer must be implemented as a separate frontend application in its own module tree.

---

# Geometry Rules

MVP supports point geometries only.

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

Search is not part of MVP.

The agent must NOT implement:

full-text search  
document search  
entity search  

unless explicitly instructed by the user.

Spatial navigation is the only discovery mechanism in MVP.

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

All BI tables are considered immutable inputs.

---

# Hierarchy Logic

Location hierarchy must support fallback:

city -> region -> country

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

hover -> preview documents  
click -> pin selection  
Esc -> reset  
click empty map -> reset  

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

The presentation layer is a single read-only service.

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