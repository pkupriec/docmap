# Phase 12 — Presentation UX Iteration 1

This phase extends phase 11.

If phase 12 conflicts with phase 11 MVP restrictions, phase 12 takes precedence for the presentation layer implementation.

This task introduces the first UX refinement pass for the DocMap presentation layer.

This task requires implementation changes across backend, frontend, schemas, and tests where necessary.

The user may choose not to edit code manually, but the implementing agent is expected to do so.

Goals:

- implement collapsible control panel
- introduce unified search
- redesign document cards
- add PDF preview functionality
- implement umbrella-style document visualization
- support mixed geometry rendering

Implementation expectation:

- update documentation where required
- update Python backend code where required
- update frontend code where required
- update automated tests where required

Non-goals:

- mobile-first redesign
- full-text content search across extracted article bodies
- geometry editing or authoring workflows
- replacing the frontend stack
- merging presentation UI into control-plane UI

State precedence for implementation:

1. pdf_modal
2. pinned_document
3. document_hover
4. search_results
5. pinned_location
6. hover_location
7. idle

Stack constraints:

- React
- TypeScript
- MapLibre GL JS
- deck.gl
- pdfjs-dist

Do not replace the frontend framework.

---

## Left Control Panel

Implement collapsible panel behavior.

Collapsed state must preserve a thin vertical bar.

---

## Search Field

Add a unified search field at the top of the document panel.

Behavior:

- trigger after >= 3 characters
- call `GET /api/search`
- limit returned suggestions/results to 5
- support canonical SCP number queries such as `SCP-1041`
- support numeric-only SCP queries such as `1041`
- support case-insensitive prefix/contains matching over location display fields
- replace location-driven document panel content with search results while search is active

Map behavior:

- a single result centers the map
- multiple results fit the bounding box of unique matched coordinates

Determinism requirements:

- results must be deterministically ordered
- duplicate documents must not appear multiple times
- duplicate locations must not appear multiple times

---

## Document Card

Contextual location must update consistently with the currently active panel result context and any viewport-driven recomputation of linked locations.

Each card must display:

- SCP number
- contextual location
- PDF thumbnail

SCP number must link to the SCP Foundation page.

---

## PDF Preview

Use pdfjs-dist.

Render first page thumbnail.

Open document inside modal overlay.

---

## Document Visualization

Hover:

- display umbrella-style lines from the hovered document card to currently visible linked locations only

Click:

- pin the document visualization

Pinned behavior:

- the map remains draggable
- as the viewport changes, visible linked locations and rendered lines must be recomputed
- newly visible linked locations appear
- no-longer-visible linked locations disappear
- offscreen linked-location count must be updated

Reset:

- click empty map to clear pinned visualization
- `Esc` also clears pinned visualization

Closing the modal must not destroy pinned document state unless another document is selected.

---

## Geometry Rendering

Support a mixed geometry model:

- country -> polygon
- region -> polygon
- city -> point

Geometry source:

- countries and regions must be loaded from static administrative boundary assets
- cities remain coordinate points from BI tables
- static administrative boundary assets should be prepared upstream (analytics-owned build step) and consumed read-only by presentation runtime

Fallback:

- if a polygon is too small for the current zoom level, render it as a point

Behavior:

- clicking a polygon must behave identically to clicking the corresponding location marker
- nested document results must be deduplicated so the panel shows unique documents

Polygon geometry must not require BI schema changes in phase 12.

Static administrative assets are the authoritative source for country/region polygons in this phase.

## Required Documentation Updates

The implementation must update these files if behavior or contracts change:

- AGENT/PRESENTATION_EXECUTION_RULES.md
- PRESENTATION_ARCHITECTURE.md
- PRESENTATION_DATA_CONTRACT.md
- PRESENTATION_UX_SPEC.md
- PRESENTATION_API_SPEC.md
- PRESENTATION_IMPLEMENTATION_PLAN.md

## Required Tests

Add or update tests for:

- search endpoint behavior
- deterministic search ordering
- document-card API payload shape
- mixed geometry contract where applicable
- existing presentation API compatibility where still intended

If existing phase 11 tests encode obsolete payload shapes or obsolete API assumptions, they must be updated as part of phase 12 implementation.

The agent must not preserve outdated test fixtures if they conflict with phase 12 contracts.

## Required Code Alignment

The implementation must align these layers with the phase 12 contracts:

- backend response schemas
- repository/query outputs
- API route behavior
- frontend state model
- frontend document card rendering
- frontend map visualization state
- automated tests

Documentation updates alone are insufficient for task completion.
