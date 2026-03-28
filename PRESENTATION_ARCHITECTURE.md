# Presentation Architecture

Coding agents should read `PRESENTATION.summary.md` first and open this file when the task needs full presentation runtime detail.

## Role

The presentation layer is an independent read-only visualization service.

Flow:
`analytics-populated BI/runtime tables -> presentation API -> presentation UI`

It does not run pipeline stages and does not write to operational, BI, or control-plane tables.

## Runtime Boundary

The presentation layer is deployed as a separate container:

- backend: `main_presentation.py` + `services/presentation/backend/*`
- frontend: `services/presentation/frontend/*` (built and served by the same presentation container)

Control plane remains separate:

- backend: `main.py` + `services/control/*`
- frontend: `ui/*`

## Runtime Data Flow

Current runtime flow:

1. analytics populates presentation-facing BI tables, including `bi_locations`, `bi_document_locations`, `bi_location_hierarchy`, and `bi_admin_boundaries`
2. presentation backend reads those tables and serves JSON/PDF responses
3. presentation frontend fetches locations and boundaries on startup
4. the UI moves from `loading` to `ready` only after both startup requests complete successfully

The current implementation is API-backed at runtime. The frontend does not currently read administrative boundary GeoJSON directly from a static frontend asset path.

## Data Inputs

Presentation backend currently reads:

- `bi_documents`
- `bi_locations`
- `bi_document_locations`
- `bi_location_hierarchy`
- `bi_admin_boundaries`
- `document_snapshots` via `bi_documents.latest_snapshot_id` when serving PDF bytes

## Boundary Delivery Model

Administrative boundaries are currently delivered through presentation API, not by direct static-file fetch in the frontend.

Current behavior:

- `GET /api/map/boundaries` assembles a `FeatureCollection`
- source table: `bi_admin_boundaries`
- repository ordering is deterministic by rank bucket, then `location_id`
- presentation remains read-only at runtime

Upstream generation/population of boundary rows may still happen outside the presentation service, but the current presentation runtime behavior is API delivery from database-backed rows.

## Hierarchy Fallback

Hierarchy fallback is resolved in backend/API logic, not in frontend heuristics.

Current implementation:

- starts with the requested location itself
- walks ancestors through `bi_location_hierarchy`
- returns the nearest depth that has linked documents
- chooses a deterministic row when multiple candidates share that depth

Important constraint:

- the code does not currently enforce a hard rank allowlist such as `city -> admin_region -> country`
- current data shape makes fallback behave like that in practice for normal cases
- `continent` and `ocean` are currently rendering ranks, not explicitly enforced fallback targets

## API Behavior

Presentation API is deterministic for identical database state:

- stable ordering in list responses
- no random sampling
- no time-dependent shaping

## Search Mode Behavior

Search is an API-backed presentation capability.

Current frontend behavior:

- search becomes active at `3+` trimmed characters
- requests are debounced by about `180 ms`
- while search is active, the right panel is driven by search results instead of location hover/pin results
- the map remains interactive while search is active

Map focus behavior:

- if search returns location results, map focus is derived from those locations
- if search returns only documents, the frontend fetches `/api/map/document/{id}/locations` for the matched documents and derives focus coordinates from those linked locations

## Location Geometry Model

The presentation layer currently supports mixed geometry rendering.

Boundary matching in the frontend currently works like this:

1. try boundary feature `location_id`
2. if that misses, fall back to `location_rank + lowercased location_name`

That rank/name fallback is implementation reality and should not be documented away.

Current rendering behavior:

- `city`:
  - polygon when a boundary exists and map zoom is `>= 3.2`
  - point when zoom is `< 3.2`
  - point when no boundary matches
- `admin_region`, `country`, `continent`, `ocean`:
  - polygon when a boundary exists
  - point when no boundary matches
- other/unknown ranks:
  - point

Current visual fallback semantics:

- missing-boundary non-city points are red
- city points remain blue when not selected, even if no boundary exists
- selected point/polygon styling uses the selected accent color

Click behavior:

- clicking a polygon behaves the same as clicking the corresponding point location

## UX Scope

The presentation UI is desktop-first.

Current implemented interactions include:

- hover preview
- pinned location selection
- API-backed search
- pinned document visualization
- PDF modal viewing
- left-panel collapse toggle
- map zoom-level widget

Reset/close sources in the current implementation:

- `Esc`: closes the PDF modal if open and also clears pinned document and pinned location state
- empty-map click: clears pinned document and pinned location state
- `Clear` button: clears pinned document, pinned location, and PDF modal state
- modal close button: closes only the modal
- click outside the PDF modal: closes only the modal
- clicking a different document card while a modal is open: closes the current modal

## State-Driven Visualization Rule

Presentation interactions are state-driven.

Current frontend state includes at least:

- `hovered_location_id`
- `pinned_location_id`
- `hovered_document_id`
- `pinned_document_id`
- `search_query`
- `search_results`
- `visible_document_links`
- `offscreen_link_count`
- `pdf_modal_document_id`
- `map_viewport`

Rendering is derived from this state rather than from ad hoc DOM-only logic.
