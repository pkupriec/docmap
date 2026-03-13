# Presentation UX Spec

## Layout

The interface consists of three regions:

- left control panel
- map viewport
- right document panel

The layout is desktop-first.

## Left Control Panel

The left panel contains map-related controls and future layer controls.

Phase 12 requirements:

- the panel must support collapsed and expanded states
- the collapsed state must remain visible as a thin vertical bar
- the collapsed bar is reserved for future layer icons

## Map Viewport

The map viewport is the primary spatial interaction surface.

The map displays:

- point locations
- mixed geometry locations
- document-link visualization
- optional overlays such as density

## Right Document Panel

The right panel displays one of these content modes:

- default instructional state
- location-driven document list
- search results
- loading state
- error state

Search results replace location-driven content while search is active.

## Interaction State Model

The UI supports these states:

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

Notes:

- search results replace right-panel content, but the map remains interactive
- pinned document must survive map drag and viewport updates
- pdf modal must not destroy pinned document state unless another document is selected

## Hover and Pin Behavior

### Hover Location

When the cursor hovers over a location and no search state is active:

- the right panel shows documents associated with that location
- hover state is transient

### Pin Location

Clicking a location pins the selection.

Pinned location behavior:

- the right panel remains fixed
- map drag remains available
- reset sources:
  - `Esc`
  - empty-map click
  - `Clear` button

### Hover Document Card

Hovering a document card renders document-to-location visualization for visible linked locations.

### Pin Document Card

Clicking a document card pins the document visualization.

Pinned document behavior:

- the visualization remains visible while the map is dragged
- visible links are recomputed as the viewport changes
- newly visible linked locations appear
- no-longer-visible linked locations disappear
- the offscreen linked-location count is updated as the viewport changes

### Empty Map Click

Clicking empty map space clears:

- pinned document
- pinned location

## Search Field

A unified search field is displayed at the top of the right panel.

Behavior:

- activates after 3 or more characters
- uses API-backed search
- supports canonical SCP number and numeric-only SCP queries
- supports case-insensitive prefix/contains matching over location display fields
- returns at most 5 suggestions/results
- search results replace location-driven right-panel content
- while search is active, `hover_location` and `pinned_location` do not replace search results in the right panel

Map synchronization rules:

- a single result centers the map and chooses an appropriate zoom level
- multiple results fit the result bounding box

## Document Card

Each document card displays:

- canonical SCP number
- contextual location
- first-page PDF thumbnail

Behavior:

- the SCP number is a link to the SCP source page
- the PDF thumbnail opens a modal viewer
- card hover and card pin control map visualization

The card remains vertically stacked in the right-panel column.

## PDF Modal

The PDF preview opens in a centered modal overlay.

Close sources:

- close button
- click outside the modal
- selecting another document

The modal close behavior must be consistent with the interaction state model and must not implicitly clear pinned document state unless another document is selected.

Rendering rules:

- first-page thumbnails are produced on the client using pdfjs-dist
- the modal must not navigate away from the presentation UI

## Document-Link Visualization

Phase 12 uses umbrella-style document-link visualization.

Rules:

- lines originate from the visual center of the document card
- lines first move vertically to a shared anchor area near the card
- from that anchor, lines spread toward visible linked locations in the map viewport
- phase 12 renders these lines immediately without animation
- the implementation must preserve an extension point for future animation

Only visible linked locations are rendered as lines in this phase.

An offscreen linked-location count must be shown in the card or associated UI.
The offscreen count updates as the viewport changes during pinned-document mode.

## Geometry Rendering

The UI supports mixed geometry rendering:

- country -> polygon
- region -> polygon
- continent -> polygon
- ocean -> polygon
- city -> point

Fallback:

- if a polygon is too small for the current zoom level, render it as a point

Click behavior for polygons must match click behavior for the corresponding point location.

Hierarchy note:

- document fallback remains `city -> region -> country`
- `continent` and `ocean` must not be added to right-panel fallback behavior in this task line

## Empty State

When neither location-driven content nor search results are active, the right panel shows:

`Explore the map to discover SCP documents.`

## Loading State

The panel shows loading indicators while API-backed content is being fetched.

## Error State

API failures show:

`Unable to load data.`

## Performance

Targets:

- hover interaction under 100 ms
- viewport-linked visualization updates remain responsive
- initial load target: 2 seconds for expected dataset

## Accessibility

Minimum keyboard support:

- `Esc` clears pinned selection
- `Esc` closes the PDF modal if open
- keyboard focus must remain usable for search input and modal close interaction
