# Presentation Architecture

## Role and Boundary

Presentation is a dedicated read-only service for map exploration.

It reads BI/runtime data and exposes:
- `/api/map/*` endpoints
- `/api/search`
- `/healthz`

It does not write operational, BI, or control-plane tables.

## Runtime Composition

- backend app: `services/presentation/backend/api.py`
- query layer: `services/presentation/backend/repository.py`
- frontend app: `services/presentation/frontend/*`
- runtime entrypoint: `main_presentation.py`

## Data Sources

- `bi_documents`
- `bi_locations`
- `bi_document_locations`
- `bi_location_hierarchy`
- `bi_admin_boundaries`
- `document_snapshots` (for PDF payloads via `latest_snapshot_id`)
- analytics-baked boundary tile artifacts:
  - `services/analytics/assets/presentation_geometry/current.json`
  - `services/analytics/assets/presentation_geometry/{version}/manifest.json`
  - `services/analytics/assets/presentation_geometry/{version}/{mode}/z/x/y.mvt`

Phase C note:
- baked geometry artifacts are now analytics-owned canonical preparation outputs.
- presentation runtime remains read-only and does not write or regenerate these artifacts.
- normal viewing now reads baked vector tiles through `/api/map/baked/manifest` and `/api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt`.
- background preload uses `/api/map/baked/tile-index` + throttled tile fetch to progressively hydrate chosen-mode geometry.
- runtime `/api/map/boundaries` remains only for selected/highlighted explicit overlay geometry.
- runtime default precision mode is configured via `DOCMAP_PRESENTATION_DEFAULT_PRECISION_MODE`.

## Document Discovery Semantics

`GET /api/map/location/{location_id}/documents` works in two steps:

1. Resolve a best location candidate for document listing (requested row or deterministic alias peer).
2. Query hierarchical descendants with a rank-scoped filter based on resolved rank.

Current scope rules:
- city -> city
- non-city ranks -> descendants from `bi_location_hierarchy` without additional rank filter

Operational implication:
- the exact non-city rank mix depends on hierarchy data materialization in BI tables.

Response includes pagination and scope metadata (`total_items`, `returned_items`, `limit`, `offset`, `scope_rank`, `scope_location_count`).

## Boundary Model

Normal-view boundary/base rendering is backed by baked vector tiles (`layer=boundaries`).

- `GET /api/map/boundaries` serves explicit live overlays from `bi_admin_boundaries` for selected/highlighted locations.
- normal-view pan/zoom no longer depends on broad live GeoJSON viewport loading.
- supporting envelope metadata in `bi_admin_boundaries`:
  - `min_lon`
  - `min_lat`
  - `max_lon`
  - `max_lat`
- envelope/index support remains analytics/startup prepared metadata, not request-time computation

## Runtime Performance Visibility

Presentation runtime emits read-path timing logs for:
- `/api/map/locations`
- `/api/map/baked/manifest`
- `/api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt`
- `/api/map/boundaries`
- `/api/map/location/{location_id}/documents`
- `/api/map/document/{document_id}/locations`
- `/api/search`

Operational intent:
- API logs capture end-to-end request timing and response payload size
- repository logs capture query/transform timing and result counts for hot paths

## Search Model

`GET /api/search` returns up to 5 documents and 5 locations.

- document ranking prioritizes canonical SCP matches
- location ranking uses normalized/city/region/country match buckets
- results are deduplicated deterministically

## PDF Delivery Model

`GET /api/map/document/{document_id}/pdf` supports HTTP byte ranges and returns:
- `200` full PDF
- `206` partial content for valid range
- `404` when PDF is unavailable
- `416` for invalid ranges
