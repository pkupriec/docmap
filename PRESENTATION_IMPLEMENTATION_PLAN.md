# Presentation Implementation Plan

## Status

Phase 11 MVP is implemented.

Phase 12 introduces the first UX refinement pass for the presentation layer and extends the MVP with:

- API-backed search
- redesigned document cards
- client-rendered PDF thumbnails and modal viewing
- pinned document visualization
- mixed geometry rendering with polygon-to-point fallback

## Delivered Structure

- backend: `services/presentation/backend/*`
- frontend: `services/presentation/frontend/*`
- runtime entrypoint: `main_presentation.py`
- container build: `Dockerfile.presentation`
- compose service: `presentation` in `infra/docker-compose.yml`

## Delivered BI Extensions

Phase 11 delivered or relied on:

- `bi_documents.preview_text`
- `bi_locations.parent_location_id`
- `bi_document_locations.evidence_quote`
- `bi_location_hierarchy`

Phase 12 may extend backend payload shaping without requiring BI write behavior in the presentation service.

## Delivered API

Phase 11 delivered:

- `GET /api/map/locations`
- `GET /api/map/location/{location_id}/documents`
- `GET /api/map/document/{document_id}/locations`
- `GET /api/map/overlays/density`
- `GET /healthz`

## Phase 12 Planned API Additions

- `GET /api/search`
- any minimal supporting document-card endpoint required by the final implementation

## Delivered UX

Phase 11 delivered:

- map-first desktop layout
- hover preview
- pinned location selection
- reset via `Esc`, empty-map click, and `Clear`
- basic document cards
- source links opening in a new browser tab

## Phase 12 Implementation Scope

- collapsible left control panel
- unified API-backed search
- redesigned document cards with contextual location
- client-rendered first-page PDF thumbnails
- centered PDF modal viewer
- umbrella-style document-to-location visualization
- viewport-aware pinned document recomputation
- mixed geometry rendering for country/region with city points

## Geometry Asset Build Integration (Phase 12 Decision)

To ensure full polygon coverage for discovered country/region locations without changing BI schema:

1. Add analytics-owned geometry asset build step.
2. Resolve unique BI location targets for `country` and `region`.
3. Match targets against static administrative boundary source datasets.
4. Emit deterministic `admin_boundaries.geojson` for presentation frontend.
5. Emit coverage diagnostics for unmatched targets.

Implementation notes for a fresh agent:

- do not generate polygons in presentation runtime
- do not move geometry responsibility into geocoder
- keep presentation read-only; it consumes generated static assets
- support stable matching keys for regions using `(country, region)` semantics to avoid name collisions
- preserve polygon-to-point fallback logic in frontend at low zoom

## Phase 12 Delivery Rules

Phase 12 is a refinement pass, not a frontend rewrite.

The agent must prefer local, incremental changes over replacing the existing presentation frontend architecture.

## Phase 12 Required Code Changes

The phase 12 implementation is expected to modify code, not only documentation.

At minimum, the implementation may need to update:

- presentation backend schemas
- presentation repository/query layer
- presentation API routes/handlers
- presentation frontend state and UI components
- presentation frontend map rendering logic
- presentation tests

Phase 12 must not be treated as a docs-only task.

Phase 12 implementation order:

1. update contracts/docs
2. implement backend search and supporting payload changes
3. implement search UI and panel-mode switching
4. implement document card redesign
5. implement PDF thumbnail generation and modal
6. implement pinned document visualization
7. implement mixed geometry rendering
8. update tests and verification docs

Backward-compatibility is allowed where useful, but phase 12 contracts are authoritative for the updated UI behavior.

If existing phase 11 payload shapes conflict with phase 12 contracts, the implementation must update the backend and tests accordingly.
