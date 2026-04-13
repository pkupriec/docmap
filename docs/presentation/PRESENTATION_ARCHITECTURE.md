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

`GET /api/map/boundaries` serves GeoJSON from `bi_admin_boundaries`.

- `lite=false` (default): full stored features
- `lite=true`: minimal properties (`location_id`, `location_name`, `location_rank`) + polygon geometry only

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
