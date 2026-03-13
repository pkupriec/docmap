# Presentation Architecture

## Role

The presentation layer is an independent read-only visualization service.

Flow:
`bi_* tables -> presentation API -> presentation UI`

It does not run pipeline stages and does not write to operational, BI, or control-plane tables.

## Runtime Boundary

The presentation layer is deployed as a separate container:

- backend: `main_presentation.py` + `services/presentation/backend/*`
- frontend: `services/presentation/frontend/*` (built and served by the same presentation container)

Control plane remains separate:

- backend: `main.py` + `services/control/*`
- frontend: `ui/*`

## Static Geometry Assets

Phase 12 loads static administrative boundary assets for countries and regions.

These assets are part of the presentation runtime and must remain separate from BI table mutation logic.

They do not change the BI contract and do not introduce write paths into the presentation service.

Authoritative phase 12 integration:

- geometry assets are generated outside presentation runtime as part of analytics-owned data preparation
- presentation only loads already-generated static assets at runtime
- geometry generation is deterministic for identical BI inputs and must not depend on UI interactions

Phase 13 extension:

- geometry assets must expand beyond the current early country/region path to cover `admin_region`, `country`, `continent`, and `ocean`
- generated geometry assets should be keyed by stable location identity such as `location_id`, not by display name alone
- stable upstream geo metadata may be required in analytics inputs to support reliable matching

## Data Inputs

Presentation backend reads only:

- `bi_documents`
- `bi_locations`
- `bi_document_locations`
- `bi_location_hierarchy`

## Hierarchy Fallback

Hierarchy fallback is resolved in backend/API logic, not in frontend heuristics.

Fallback order:
`city -> region -> country`

Implementation source:

- parent links: `bi_locations.parent_location_id`
- ancestor mapping: `bi_location_hierarchy`

Phase 13 note:

- `continent` and `ocean` are rendering ranks only
- they must not participate in document fallback unless the user explicitly changes that decision

## API Behavior

Presentation API is deterministic for identical BI table state:

- stable ordering in all list responses
- no random sampling
- no time-dependent shaping

## Search Mode Behavior

Search is an API-backed presentation capability.

When search is active:

- the right panel is driven by search results instead of location hover/pin results
- the map remains interactive
- viewport updates are driven by returned result coordinates

## Location Geometry Model

The presentation layer supports mixed geometry rendering.

Geometry hierarchy:

- country -> polygon
- region -> polygon
- continent -> polygon
- ocean -> polygon
- city -> point

Geometry fallback rules:

- if polygon geometry is too small for the current zoom level, it may be rendered as a point

Click behavior:

- clicking a polygon must behave identically to clicking the corresponding location marker

Administrative boundary geometries must be loaded from static GeoJSON datasets or equivalent static runtime assets.

Countries and regions are rendered as polygons in phase 12 when geometry exists.
Continents and oceans are planned polygon ranks in phase 13.

Cities remain point locations.

## UX Scope

The presentation UI is desktop-first.

Phase 11 baseline interactions:

- hover preview
- pinned location selection

Phase 12 extends the interaction model with:

- API-backed search results
- pinned document visualization
- PDF modal viewing

Phase 13 preserves the phase 12 interaction model while extending geometry coverage.

Reset/close sources:

- `Esc`
- empty-map click
- `Clear` button
- modal close button
- click outside the PDF modal

## State-Driven Visualization Rule

State precedence must follow `PRESENTATION_UX_SPEC.md` and the presentation task files.

Later presentation task files may extend the phase 11 MVP interaction model without rewriting the overall presentation architecture.

Presentation interactions must be state-driven.

At minimum, the frontend architecture must model:

- hovered_location_id
- pinned_location_id
- hovered_document_id
- pinned_document_id
- search_query
- search_results
- visible_document_links
- pdf_modal_document_id

Rendering must be derived from this state instead of ad hoc DOM-driven logic.
