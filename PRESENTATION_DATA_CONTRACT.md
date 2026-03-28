# Presentation Data Contract

Coding agents should read `PRESENTATION.summary.md` first and open this file when the task needs the detailed presentation data contract.

## Scope

This contract documents the current implemented presentation payloads and the weaker guarantees that the current code actually enforces.

All IDs are UUID strings in API payloads.

## Source Tables

Presentation currently reads from:

- `bi_documents`
- `bi_locations`
- `bi_document_locations`
- `bi_location_hierarchy`
- `bi_admin_boundaries`
- `document_snapshots` indirectly through `bi_documents.latest_snapshot_id`

## Location Contract

Source: `bi_locations`

Fields returned by API:

- `location_id` (UUID)
- `name` (`bi_locations.normalized_location`)
- `latitude` (float)
- `longitude` (float)
- `precision` (string|null)
- `location_rank` (string|null)
- `document_count` (int)
- `parent_location_id` (UUID|null)

Observed/expected `location_rank` values:

- `city`
- `admin_region`
- `region` may still appear in older or upstream data and is normalized to `admin_region` in the frontend
- `country`
- `continent`
- `ocean`
- `unknown`

## Document Card Contract

Primary sources:

- `bi_documents`
- `bi_document_locations`

PDF availability source:

- `bi_documents.latest_snapshot_id`
- `document_snapshots.pdf_blob`

Fields returned by API:

- `document_id` (UUID)
- `scp_number` (string)
- `canonical_scp_id` (string)
- `scp_url` (string)
- `location_display` (string|null)
- `pdf_url` (string|null)

Derived in frontend:

- `pdf_preview_thumbnail` (client-rendered first-page thumbnail generated from `pdf_url` via `pdfjs-dist`)

Current notes:

- `pdf_preview_thumbnail` is not a persisted field
- `pdf_url` is present only when `latest_snapshot_id` exists and the API can route `/api/map/document/{id}/pdf`
- `GET /api/map/document/{id}` and `/api/search` derive `location_display` from the top linked location by `mention_count DESC`
- `GET /api/map/location/{id}/documents` overwrites `location_display` with the resolved fallback location name

## Document-Location Link Contract

Source:

- `bi_document_locations`
- `bi_locations`

Fields:

- `document_id` (UUID)
- `location_id` (UUID)
- `name` (string)
- `latitude` (float)
- `longitude` (float)
- `precision` (string|null)
- `location_rank` (string|null)
- `evidence_quote` (string|null)
- `mention_count` (int)

## Hierarchy Contract

Source: `bi_location_hierarchy`

Fields:

- `ancestor_location_id` (UUID)
- `descendant_location_id` (UUID)
- `depth` (int)

Depth semantics:

- `0` = self
- `1` = parent
- `2+` = higher ancestor

## Fallback Result Contract

`GET /api/map/location/{id}/documents` returns:

- `requested_location_id` (UUID)
- `resolved_location_id` (UUID|null)
- `fallback_depth` (int|null)
- `items` (`DocumentCard[]`)

Current fallback semantics:

- the backend resolves the nearest ancestor depth with documents, including the requested location itself
- this is implemented through `bi_location_hierarchy`, not by a hardcoded rank ladder
- current data shape usually makes fallback look like `city -> admin_region -> country`
- `fallback_depth` is `null` when no location resolves

`continent` and `ocean` are not specially handled as fallback targets by the current code.

## Search Result Contract

Source: presentation API search response

### SearchDocumentResult

- `document_id` (UUID)
- `scp_number` (string)
- `canonical_scp_id` (string)
- `scp_url` (string)
- `location_display` (string|null)
- `pdf_url` (string|null)

### SearchLocationResult

- `location_id` (UUID)
- `name` (string)
- `latitude` (float)
- `longitude` (float)
- `precision` (string|null)
- `location_rank` (string|null)
- `document_count` (int)
- `parent_location_id` (UUID|null)

Current API limit behavior:

- up to `5` documents
- up to `5` locations

## Boundary Geometry Contract

Source: `GET /api/map/boundaries`

Payload:

- GeoJSON `FeatureCollection`
- features sourced from `bi_admin_boundaries.feature_json`

Current feature properties may include:

- `location_id` (string, optional but preferred)
- `location_name` (string)
- `location_rank` (string)
- `country_name` (string|null)
- `region_name` (string|null)
- `match_strategy` (string, informational metadata)

Current frontend matching behavior:

1. match boundary by `location_id`
2. if that fails, match by `location_rank + lowercased location_name`

That second step is a current implementation fallback, not a strong identity guarantee.

## Geometry Rendering Contract

Current rendering can use either:

- point geometry from location coordinates
- polygon geometry from `/api/map/boundaries`

Current rules:

- `city` renders as a polygon only when a matching boundary exists and zoom is `>= 3.2`
- `city` falls back to a point at lower zoom or when no boundary matches
- `admin_region`, `country`, `continent`, and `ocean` render as polygons when a matching boundary exists
- missing-boundary non-city locations fall back to red points
- city fallback points remain blue when not selected
- unknown/other ranks render as points

The current frontend uses only `Polygon` and `MultiPolygon` features.

## Runtime Visualization State

The following values are UI runtime state, not persisted API fields:

- `hovered_location_id`
- `pinned_location_id`
- `hovered_document_id`
- `pinned_document_id`
- `visible_document_links`
- `offscreen_link_count`
- `search_active`
- `pdf_modal_document_id`
- `map_viewport`
