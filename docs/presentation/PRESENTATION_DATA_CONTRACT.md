# Presentation Data Contract

All IDs are UUID strings in API payloads.

## Location Object (`GET /api/map/locations`)

Fields:
- `location_id`
- `name`
- `latitude`
- `longitude`
- `precision`
- `location_rank`
- `document_count`
- `parent_location_id`

## Document Card Object

Fields:
- `document_id`
- `scp_number`
- `canonical_scp_id`
- `scp_url`
- `location_display`
- `pdf_url`

`pdf_url` is populated only when `bi_documents.latest_snapshot_id` exists.

## Location -> Documents Response (`GET /api/map/location/{location_id}/documents`)

Fields:
- `requested_location_id`
- `resolved_location_id`
- `fallback_depth`
- `scope_rank`
- `scope_location_count`
- `total_items`
- `returned_items`
- `limit`
- `offset`
- `items` (`DocumentCard[]`)

Notes:
- `fallback_depth` is alias-resolution depth from repository logic, not hierarchy depth.
- `total_items` is full result count before paging.
- `returned_items` is the page item count after dedupe.
- For non-city scopes, document aggregation uses selected geometry + recursive descendants from `bi_location_hierarchy`.
- City scope remains city-only unless city polygons/hierarchy descendants exist.

## Document -> Locations Response (`GET /api/map/document/{document_id}/locations`)

Fields:
- `document_id`
- `location_id`
- `name`
- `latitude`
- `longitude`
- `precision`
- `location_rank`
- `evidence_quote`
- `mention_count`

## Boundaries Response (`GET /api/map/boundaries`)

GeoJSON `FeatureCollection` from `bi_admin_boundaries.feature_json`.

`lite=true` returns a reduced feature payload.

## Search Response (`GET /api/search`)

Shape:
- `query`
- `documents` (max 5)
- `locations` (max 5)

Short-query behavior:
- frontend triggers search for 3+ characters
- repository returns empty arrays when trimmed query length is below 3
