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

## API Behavior

Presentation API is deterministic for identical BI table state:

- stable ordering in all list responses
- no random sampling
- no time-dependent shaping

## Geometry Scope

MVP supports point geometries only:

- `latitude`
- `longitude`

No polygons or uncertainty radii in phase 11.

## UX Scope

Desktop-first map UI with two interaction states:

- hover preview
- pinned selection

Reset sources:

- `Esc`
- empty-map click
- `Clear` button

