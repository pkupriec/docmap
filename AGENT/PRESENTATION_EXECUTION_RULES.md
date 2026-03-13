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
18. TASKS/phase12_presentation_ux_iteration_1.md
19. TASKS/phase12_code_alignment.md
20. TASKS/phase12_execution_checklist
21. TASKS/phase13_map_geometry.md
22. AGENT/MAP_GEOMETRY_HANDOFF.md

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

Phase 12 supports a mixed geometry model.

Allowed geometry behavior:

- country -> polygon
- region -> polygon
- city -> point
- continent -> polygon (phase 13)
- ocean -> polygon (phase 13)

Geometry source rules:

- country and region geometries must come from static administrative boundary datasets
- continent and ocean geometries must also come from static upstream datasets in phase 13
- geometry loading must remain read-only
- geometry datasets must not be generated heuristically in the frontend
- geometry dataset preparation should be implemented as an upstream build step (phase 12 decision: analytics-owned generation), not as presentation runtime mutation logic
- geometry assets should be matched to presentation locations by stable identity, not by display name alone

Fallback rules:

- if a polygon is too small or visually insignificant at the current zoom level, it must be rendered as a point
- city locations remain points in this phase
- hierarchy fallback remains `city -> region -> country`
- `continent` and `ocean` are rendering ranks only and must not be added to fallback logic

Forbidden geometry behavior:

- no geometry editing
- no uncertainty radii
- no freeform polygon generation
- no frontend-only inferred hierarchy

Click behavior:

- clicking a rendered polygon must behave identically to clicking the corresponding location marker

---

# PDF Rules
Document preview thumbnails must be rendered using pdfjs-dist.

The first page of the PDF must be used to generate a thumbnail preview inside document cards.

PDF documents must open inside a modal viewer without navigating away from the map interface.

Visualization implementation must preserve an extension point for future animation.

Phase 12 renders document-link visualizations immediately without animation, but the implementation must not hard-code an approach that prevents later animated transitions.

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

The UI must support these high-level states:

- idle
- hover_location
- pinned_location
- search_results
- document_hover
- pinned_document
- pdf_modal
- loading
- error

State precedence rules:

- pdf_modal overrides card hover rendering but must not destroy the pinned document state
- search_results overrides location-driven right-panel content
- pinned_document overrides transient document hover
- pinned_location overrides hover_location

Behavior rules:

- hover over a location previews location documents in the right panel unless search is active
- click on a location pins the location selection
- hover over a document card shows document-to-visible-location visualization
- click on a document card pins that visualization
- clicking empty map space clears pinned document and pinned location state
- Esc clears pinned selection and closes the PDF modal if open

Document cards must:

- display canonical SCP number
- link the SCP number to the SCP source page
- display contextual location
- display first-page PDF thumbnail

---

---

# Search Rules

Search functionality is part of phase 12.

Search must be implemented through the presentation API.

Client-side-only search implementations are not allowed.

Search interaction rules:

- search results are independent from hover and pinned location state
- when search is active, the right panel shows search results instead of location-driven results
- search responses must be served by the presentation API
- when multiple search results are returned, the map must fit the result bounding box
- when a single search result is returned, the map must center on that result and choose an appropriate zoom level
- search responses must be deterministically ordered
- duplicate documents must not appear multiple times
- duplicate locations must not appear multiple times

# Forbidden Architecture Changes

The agent must not introduce:

message brokers  
task queues  
background workers  
microservice splits  
data mutation pipelines  

The presentation layer is a single read-only service.

The geometry asset generator may exist as code in the repository, but its execution must not introduce presentation write behavior at runtime.

---

# Development Strategy

The agent must implement in this order:

1. update presentation contracts and documentation for phase 12
2. add BI/API fields required by document cards and search
3. implement search endpoint and deterministic search ordering
4. add geometry asset loading contract
5. implement UI shell updates (collapsible left panel, search field, right panel states)
6. implement document card redesign
7. implement PDF thumbnail rendering and modal viewer
8. implement document hover/pin visualization state model
9. implement mixed geometry rendering and point fallback
10. integrate viewport-aware recomputation of document-location lines
11. add/update tests
12. refresh documentation

Implementation note:

If phase 12 contracts require backend/API/schema/test updates, the agent must make those code changes.
The user restriction in the review process applies to manual edits only and does not prohibit agent-driven implementation changes.

Markdown authority note:

- `GPT-5.4` may update project markdown files.
- `gpt-5.3-codex` and other non-`GPT-5.4` models must treat markdown as fixed execution instructions and implement code/tests accordingly without rewriting the docs.

---

# Success Criteria

The implementation is considered complete when:

- the presentation UI renders map locations and mixed geometry according to phase 12 rules
- search is available through the presentation API
- search results replace the right panel content and update map viewport
- document cards display SCP number, contextual location, and PDF thumbnail
- clicking the SCP number opens the SCP source page
- clicking the PDF preview opens a modal viewer
- hovering a document card renders umbrella-style links to visible locations
- clicking a document card pins the visualization
- empty-map click resets pinned document and pinned location state
- geometry click behavior matches location marker click behavior
- API reads BI tables and static geometry assets only
- no writes occur in the presentation service
- phase 13 geometry work, when in scope, preserves `city -> region -> country` fallback and treats `continent`/`ocean` as rendering ranks only

The implementation must also update backend schemas, repository/query logic, API handlers, frontend state, and tests wherever required to satisfy the active presentation contracts.
