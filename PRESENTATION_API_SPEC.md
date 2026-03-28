# Presentation API Spec

Coding agents should read `PRESENTATION.summary.md` first and open this file when the task needs the detailed API contract.

## Scope

Read-only API for the presentation map UI.

Base paths:

- map endpoints: `/api/map/*`
- search: `/api/search`
- health: `/healthz`

## GET `/api/map/locations`

Returns all valid coordinate-bearing locations from `bi_locations` with deterministic ordering.

Response: `Location[]`

Returned fields currently include:

- `location_id`
- `name`
- `latitude`
- `longitude`
- `precision`
- `location_rank`
- `document_count`
- `parent_location_id`

## GET `/api/map/boundaries`

Returns presentation boundary geometry as a GeoJSON `FeatureCollection`.

Runtime source:

- `bi_admin_boundaries.feature_json`

Current response characteristics:

- all rows are assembled into one `FeatureCollection`
- response ordering is deterministic by rank bucket, then `location_id`
- only `Polygon` and `MultiPolygon` features are usable by the current frontend

Current feature properties may include:

- `location_id`
- `location_name`
- `location_rank`
- `country_name`
- `region_name`
- `match_strategy`

## GET `/api/map/location/{location_id}/documents`

Returns documents for a location with backend hierarchy fallback.

Path parameter:

- `location_id` UUID

Response:

```json
{
  "requested_location_id": "uuid",
  "resolved_location_id": "uuid-or-null",
  "fallback_depth": 0,
  "items": []
}
```

Fallback behavior:

- direct location first
- if empty: nearest ancestor depth in `bi_location_hierarchy` that has linked documents
- if nothing resolves: `resolved_location_id = null`, `fallback_depth = null`, `items = []`

Important note:

- current implementation does not enforce a strict fallback rank allowlist in SQL
- current data shape makes results behave like `city -> admin_region/country` in practice

## GET `/api/map/document/{document_id}`

Returns a single document card payload suitable for:

- right-panel rendering
- modal coordination
- search result cards

Response fields:

- `document_id`
- `scp_number`
- `canonical_scp_id`
- `scp_url`
- `location_display`
- `pdf_url`

## GET `/api/map/document/{document_id}/pdf`

Returns PDF bytes for a document when a latest snapshot with `pdf_blob` exists.

Current source path:

- `bi_documents.latest_snapshot_id -> document_snapshots.pdf_blob`

Response:

- `application/pdf` on success
- `404 {"error":"not_found"}` when no PDF payload exists

## GET `/api/map/document/{document_id}/locations`

Returns linked locations for a document.

Path parameter:

- `document_id` UUID

Response: `DocumentLocationLink[]`

Current ordering:

- `mention_count DESC`
- `name ASC`
- `location_id ASC`

## GET `/api/map/overlays/density`

Returns density points from `bi_locations`.

Response: `DensityPoint[]`

## GET `/api/search`

Performs deterministic presentation search for:

- canonical SCP numbers
- numeric-only SCP queries
- document top-location display text
- location display fields from `bi_locations`

Query parameters:

- `q`: string, required, API validates minimum length `1`
- `limit`: integer, optional, default `5`, maximum `5`

Activation and short-query behavior:

- the frontend only calls this endpoint after `3+` trimmed characters
- repository search returns empty `documents` and `locations` arrays for trimmed queries shorter than `3`

Current response shape:

```json
{
  "query": "paris",
  "documents": [],
  "locations": []
}
```

Current limits:

- backend caps documents to at most `5`
- backend caps locations to at most `5`

Ordering rules currently implemented:

- document results are bucketed by canonical-number exact/prefix/contains and then location-display matches
- numeric-only canonical matches outrank broader text matches
- location results are bucketed by exact and contains matches across normalized location, city, region, and country fields
- ties are resolved deterministically

Deduplication rules:

- duplicate documents are removed by `document_id`
- duplicate locations are removed by `location_id`

## Search Result Viewport Behavior

Viewport fitting is a frontend behavior driven by search response content.

Current rules:

- if search returns one or more location results, the frontend fits/centers using those locations only
- if search returns no location results but does return documents, the frontend fetches `/api/map/document/{id}/locations` for the matched documents and computes focus coordinates from the linked locations
- coordinates are deduplicated before focus/fit decisions
- a single coordinate recenters the map
- multiple coordinates fit a bounding box

## API Read-Only Guarantee

The presentation API is read-only.

Current implementation detail:

- geometry is served by the API from DB-backed boundary rows
- the API does not mutate or regenerate geometry at request time
