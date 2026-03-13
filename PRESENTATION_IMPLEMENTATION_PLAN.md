# Presentation Implementation Plan

## Status

Phase 11 MVP is implemented.

Phase 12 introduces the first UX refinement pass for the presentation layer and extends the MVP with:

- API-backed search
- redesigned document cards
- client-rendered PDF thumbnails and modal viewing
- pinned document visualization
- mixed geometry rendering with polygon-to-point fallback

Phase 13 introduces real-geometry map coverage refinement with:

- reliable geometry matching by stable location identity
- `location_rank`-driven rendering
- polygon support for `continent` and `ocean`
- preservation of existing fallback semantics (`city -> region -> country`)

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

Phase 13 is expected to add planned rank/identity support needed for reliable geometry matching.

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

## Phase 13 Planned API Additions

- `location_rank` in location-oriented payloads
- any minimal contract additions required to support identity-based geometry matching

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

To ensure polygon coverage for discovered country/region locations without changing BI schema:

1. Add analytics-owned geometry asset build step.
2. Resolve unique BI location targets for `country` and `region`.
3. Match targets against static administrative boundary source datasets.
4. Emit deterministic `admin_boundaries.geojson` for presentation frontend.
5. Emit coverage diagnostics for unmatched targets.

Implementation notes:

- do not generate polygons in presentation runtime
- do not move geometry responsibility into presentation runtime
- keep presentation read-only; it consumes generated static assets
- support stable matching keys for regions using `(country, region)` semantics to avoid name collisions
- preserve polygon-to-point fallback logic in frontend at low zoom

## Geometry Asset Build Integration (Phase 13 Extension)

Phase 13 implementation must refine the phase 12 geometry approach:

1. Replace stub or low-coverage source data with real upstream geometry datasets.
2. Match generated geometry to presentation locations using stable identity rather than display name alone.
3. Extend supported polygon ranks to `admin_region`, `country`, `continent`, and `ocean`.
4. Keep `city` as point geometry.
5. Preserve hierarchy fallback as `city -> region -> country` only.

## Delivery Rules

Phase 12 and phase 13 are refinement passes, not frontend rewrites.

The agent must prefer local, incremental changes over replacing the existing presentation frontend architecture.

## Required Code Changes

At minimum, the implementation may need to update:

- presentation backend schemas
- presentation repository/query layer
- presentation API routes/handlers
- presentation frontend state and UI components
- presentation frontend map rendering logic
- presentation tests
- analytics geometry asset generation
- geocoder metadata persistence if needed for stable identity

## Phase 12 Implementation Order

1. update contracts/docs
2. implement backend search and supporting payload changes
3. implement search UI and panel-mode switching
4. implement document card redesign
5. implement PDF thumbnail generation and modal
6. implement pinned document visualization
7. implement mixed geometry rendering
8. update tests and verification docs

## Phase 13 Implementation Order

1. update phase 13 contracts/tasks/docs
2. extend schema and geocoder metadata needed for stable geo identity
3. extend analytics BI projection and geometry target shaping
4. rebuild static geometry asset generation with coverage diagnostics
5. update presentation API/frontend contracts for `location_rank`
6. switch frontend geometry matching to stable identity
7. verify polygon rendering and preserved UX behavior

Markdown governance for phase 13:

- `GPT-5.4` may update markdown contracts/tasks/specs.
- `gpt-5.3-codex` should treat those markdown files as fixed execution instructions while implementing the code.
