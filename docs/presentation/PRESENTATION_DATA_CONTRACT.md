# Presentation Data Contract

All IDs are UUID strings in API payloads.

## Analytics Baked Geometry Artifact Contract (Phase B)

Canonical artifact root:
- `services/analytics/assets/presentation_geometry/`

Pointer:
- `current.json`
  - `current_version`
  - `manifest` (relative manifest path)

Version manifest:
- `{version}/manifest.json`
  - `schema_version`
  - `version`
  - `tile_format` (`mvt_zxy_directory`)
  - `source_table` (`bi_admin_boundaries`)
  - `zoom_min`
  - `zoom_max`
  - `modes`:
    - `full_precise`
    - `balanced_precise`
    - `simplified`
    - `primitive`
  - per mode:
    - `path` (`{version}/{mode}`)
    - `tile_count`
    - `byte_size`
    - `tolerance_by_zoom_band` (`world`, `regional`, `local`)

Tile payload contract:
- path shape: `{version}/{mode}/{z}/{x}/{y}.mvt`
- layer name: `boundaries`
- feature properties are minimal and stable:
  - `location_id`
  - `location_rank`
  - `location_name`
- `Full precise` mode is unsimplified (`tolerance=0` across zoom bands)
- simplification policy is zoom-band-only (no rank-tuned simplification)

Baked manifest API (`GET /api/map/baked/manifest`) returns:
- `mode`: active mode used for the response tile template
- `default_mode`: runtime default precision mode
- `available_modes`: selectable session modes

Baked tile index API (`GET /api/map/baked/tile-index`) returns:
- `version`
- `mode`
- `tile_count`
- `tiles`: deterministic `z/x/y` list used for throttled background preload

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
- unresolved location requests return `200` with `resolved_location_id=null` and empty `items`.
- For non-city scopes, document aggregation uses recursive descendants from `bi_location_hierarchy` for the resolved location.
- City scope applies a city-only rank filter.

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

Runtime support columns in `bi_admin_boundaries`:
- `min_lon`
- `min_lat`
- `max_lon`
- `max_lat`

Query params:
- `lite` (`false` default): reduced feature payload when `true`.
- `rank_filter` (`default` default): `default|all` compatibility selector when `ranks` is omitted.
- `ranks` (optional): explicit rank list. `region` is normalized to `admin_region`.
- `selected_location_id` (optional): explicit UUID to include in the live overlay set.
- `highlighted_location_ids` (optional): explicit UUID list to include in the live overlay set.
- `chunk_ids` / `viewport_bucket` / `bbox` are accepted by API shape but are not part of the normal-view rendering path after Phase C cutover.

Behavior notes:
- presentation serves full stored geometry only; there is no reduced-detail mode.
- normal viewing uses baked vector tiles, not this endpoint.
- `GET /api/map/boundaries` is reserved for selected/highlighted explicit live overlays.
- boundary filtering uses the baked envelope columns above plus supporting indexes on `(min_lat, max_lat)` and `(min_lon, max_lon)` when spatial selectors are provided.
- `chunk_ids`, `viewport_bucket`, and `bbox` remain mutually exclusive request shapes.
- when `ranks` is omitted, `rank_filter=default` uses the default presentation ranks and `rank_filter=all` allows all stored ranks.
- explicitly selected/highlighted polygons are included even when they fall outside `bbox`.
- duplicate polygons for the same `location_id` are suppressed before response emission.

## Search Response (`GET /api/search`)

Shape:
- `query`
- `documents` (max 5)
- `locations` (max 5)

Short-query behavior:
- frontend triggers search for 3+ characters
- repository returns empty arrays when trimmed query length is below 3
