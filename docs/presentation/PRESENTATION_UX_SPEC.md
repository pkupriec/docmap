# Presentation UX Spec

Coding agents should read `PRESENTATION.summary.md` first and open this file when the task needs exact interaction semantics.

## Layout

The interface consists of three regions:

- left control panel
- map viewport
- right document panel

The layout is desktop-first.

## Left Control Panel

The current left panel contains:

- collapse/expand toggle
- `DocMap` title
- `Presentation Layer` caption
- location count
- `Clear` button

Current collapsed behavior:

- the panel collapses to a thin vertical strip
- the collapse toggle remains visible
- compact quick actions are available in collapsed mode (search focus and clear)

## Map Viewport

The map viewport is the primary spatial interaction surface.

The current map displays:

- point locations
- polygon boundaries for matched locations
- document-link visualization
- in-map legend describing current geometry/marker semantics
- zoom controls
- a visible zoom-level widget

## Right Document Panel

The right panel displays one of these current content modes:

- default instructional state
- location-driven document list
- search-driven results
- shared loading state
- shared error state

Search results replace location-driven content while search is active.

## Interaction State Model

The UI currently supports these states:

- idle
- hover_location
- pinned_location
- search_results
- document_hover
- pinned_document
- pdf_modal
- loading
- error

State precedence:

1. `pdf_modal`
2. `pinned_document`
3. `document_hover`
4. `search_results`
5. `pinned_location`
6. `hover_location`
7. `idle`

Current notes:

- search results replace right-panel content, but the map remains interactive
- pinned document survives map drag and viewport updates
- visible and offscreen linked-document counts are recomputed as viewport changes
- modal close behavior is not uniform across all close paths:
  - modal close button and backdrop click close only the modal
  - `Esc` closes the modal if open and also clears pinned document and pinned location state

## Startup and Global Fetch Behavior

Current startup behavior:

- the frontend starts in `loading`
- it fetches locations first for initial UI readiness
- boundaries are fetched in background and hydrate map overlays when available
- the UI becomes `ready` after locations load successfully

Current error behavior:

- startup failure shows `Unable to load locations.`
- location-document fetch failure shows `Unable to load linked documents for this location.`
- search failure shows `Unable to load search results.`
- boundaries-only failure is non-fatal and shows `Boundaries unavailable. Showing location points only.`

## Hover and Pin Behavior

### Hover Location

When the cursor hovers over a location and search is not active:

- the right panel shows documents associated with that location
- hover state is transient

When search is active:

- the map can still highlight/interact with locations
- the right panel remains driven by search results instead of hover content

### Pin Location

Clicking a location pins the selection.

Pinned location behavior:

- the map selection remains fixed until cleared
- map drag remains available
- if search is active, pinning still updates map selection but does not replace search results in the right panel

Reset sources:

- `Esc`
- empty-map click
- `Clear` button

### Hover Document Card

Hovering a document card renders document-to-location visualization for currently visible linked locations.

### Pin Document Card

Clicking a document card toggles pinned document visualization.

Pinned document behavior:

- the visualization remains visible while the map is dragged
- visible links are recomputed as the viewport changes
- newly visible linked locations appear
- no-longer-visible linked locations disappear
- offscreen linked-location count updates as the viewport changes

### Empty Map Click

Clicking empty map space clears:

- pinned document
- pinned location

## Search Field

A unified search field is displayed at the top of the right panel.

Current behavior:

- activates after `3+` trimmed characters
- requests are debounced by about `180 ms`
- uses API-backed search
- supports canonical SCP number and numeric-only SCP queries
- supports case-insensitive matching over document top-location display and location display fields
- backend returns at most `5` document results and `5` location results
- search results replace location-driven right-panel content
- while search is active, `hover_location` and `pinned_location` do not replace search results in the right panel
- right panel shows a small query/result summary while search is active

Map synchronization rules:

- if search returns one or more location results, the map centers/fits using those locations
- if search returns only documents, the frontend fetches document-linked locations and fits the map using deduplicated linked coordinates

## Document Card

Each current document card displays:

- canonical SCP number
- contextual location
- first-page PDF thumbnail or `No PDF preview`

Behavior:

- the SCP number is a link to the SCP source page in a new tab
- hovering the card previews document-link visualization
- clicking the card toggles pinned document state
- clicking the PDF thumbnail pins the document and opens the modal
- when a different document card is clicked while a PDF modal is open, the current modal closes

The card remains vertically stacked in the right-panel column.

Card readability refinements:

- compact metadata pills provide quick status cues
- active visualization cards show emphasized state markers
- offscreen linked-location count is rendered as a badge

## PDF Modal

The PDF preview opens in a centered modal overlay.

Rendering rules:

- modal content is an `iframe`
- iframe source is `/api/map/document/{id}/pdf`
- the modal does not navigate away from the presentation UI
- first-page thumbnails are produced on the client using `pdfjs-dist`

Close sources:

- close button
- click outside the modal
- pressing `Esc`
- clicking a different document card while a modal is open

Current state interaction detail:

- close button and backdrop click close only the modal
- `Esc` closes the modal if open and also clears pinned document and pinned location state

## Document-Link Visualization

The current UI uses umbrella-style document-link visualization.

Rules:

- lines originate from the visual center of the active document card
- lines first move vertically to a shared anchor area near the card
- from that anchor, lines spread toward visible linked locations in the map viewport
- lines use a short transition for smoother entry/exit
- line opacity/width are emphasis-weighted for readability
- an optional declutter mode limits rendered visible links to top-ranked entries

Only visible linked locations are rendered as lines in the current implementation.

An offscreen linked-location count is shown for the active visualization document.
The offscreen count updates as the viewport changes during hover or pinned-document mode.

## Geometry Rendering

The current UI supports mixed geometry rendering.

Current rank behavior:

- `city`:
  - polygon when a matching boundary exists and zoom is `>= 3.2`
  - point when zoom is `< 3.2`
  - point when no boundary matches
- `admin_region`, `country`, `continent`, `ocean`:
  - polygon when a matching boundary exists
  - point when no boundary matches
- other/unknown:
  - point

Current matching behavior:

- boundary match first tries `location_id`
- then falls back to `location_rank + location_name`

Current visual fallback semantics:

- boundary-unavailable non-city points use a neutral blue point style
- city points remain blue when not selected

Click behavior for polygons matches click behavior for the corresponding location point.

Hierarchy note:

- document fallback currently resolves to the nearest ancestor with documents
- in current data this usually behaves like `city -> admin_region -> country`
- that rank ladder is weaker than a strict implementation guarantee

## Empty State

When neither location-driven content nor search results are active, the right panel shows:

`Explore the map to discover SCP documents.`

If a location/search context exists but there are no document cards to show, the panel shows:

`No linked documents.`

## Loading State

The shared startup loading state shows:

`Loading locations and boundaries...`

## Error State

API failures currently show:

contextual messages by failure scope instead of one generic message

## Performance Notes

Current implementation realities to preserve during optimization work:

- startup no longer waits on boundaries payload
- default boundaries request uses full-detail default (`GET /api/map/boundaries?lite=1&rank_filter=default`)
- map movement currently causes frequent viewport-driven recomputation
- PDF thumbnails are generated client-side from PDF URLs

## Accessibility

Current keyboard behavior:

- `Esc` clears pinned document and pinned location state
- if the PDF modal is open, the same `Esc` press also closes it
- keyboard focus remains usable for the search input and modal close button
