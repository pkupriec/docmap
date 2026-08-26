# Presentation API Spec

Base URL in local compose: `http://localhost:8080`.

## Endpoints

- `GET /healthz`
- `GET /api/map/locations`
- `GET /api/map/baked/manifest?mode={full_precise|balanced_precise|simplified|primitive}`
- `GET /api/map/baked/tile-index?mode={full_precise|balanced_precise|simplified|primitive}`
- `GET /api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt`
- `GET /api/map/boundaries?lite={bool}&rank_filter={default|all}&ranks={csv}&chunk_ids={csv}&viewport_bucket={band:west:south:east:north}&bbox={west,south,east,north}&selected_location_id={uuid}&highlighted_location_ids={uuid,...}`
- `GET /api/map/location/{location_id}/documents?limit={1..300}&offset={>=0}`
- `GET /api/map/document/{document_id}`
- `GET /api/map/document/{document_id}/pdf`
- `GET /api/map/document/{document_id}/locations`
- `GET /api/map/overlays/density`
- `GET /api/search?q={text}&limit={1..5}`

## Response Guarantees

- deterministic ordering for identical DB state
- UUIDs serialized as strings
- document and location search results deduplicated by ID

## Error Shape

For not-found single-document resources:

```json
{"error": "not_found"}
```

Current behavior notes:
- `GET /api/map/document/{document_id}` and `GET /api/map/document/{document_id}/pdf` return `404` with the error shape above when missing.
- `GET /api/map/location/{location_id}/documents` returns `200` with empty scoped payload when location is unresolved (it does not return `404`).
- normal view geometry is sourced from baked endpoints (`/api/map/baked/manifest`, `/api/map/baked/tiles/...`).
- `GET /api/map/boundaries` is reserved for explicit selected/highlighted live overlays.
- boundaries responses are cached in-process for 10 minutes per canonical request shape (`lite`, `rank_filter`, `ranks`, `chunk_ids|viewport_bucket|bbox`, `selected_location_id`, `highlighted_location_ids`).
- presentation runtime logs request timing and payload size for:
  - `/api/map/locations`
  - `/api/map/baked/manifest`
  - `/api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt`
  - `/api/map/boundaries`
  - `/api/map/location/{location_id}/documents`
  - `/api/map/document/{document_id}/locations`
  - `/api/search`

## Baked Geometry Endpoints

- `GET /api/map/baked/manifest`
  - query: `mode` (optional)
  - response includes: `version`, `mode`, `default_mode`, `available_modes`, `tile_url_template`, `zoom_min`, `zoom_max`, and tolerance metadata.
  - when `mode` is omitted, `mode` resolves to runtime default precision configured by `DOCMAP_PRESENTATION_DEFAULT_PRECISION_MODE` when valid; otherwise it falls back to the first available mode.
- `GET /api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt`
  - serves vector tile payload (`application/vnd.mapbox-vector-tile`) when present.
  - returns `404` when the requested tile is absent.
- `GET /api/map/baked/tile-index`
  - query: `mode` (optional)
  - response includes: `version`, `mode`, `tile_count`, and deterministic tile coordinate list (`z/x/y`) for controlled background preload.

## Boundaries Query Parameters (Explicit Live Overlay Path)

- `lite` (default `false`): minimal boundary properties payload.
- `rank_filter` (default `default`): compatibility selector for default map ranks vs. all stored ranks when `ranks` is omitted.
- `ranks` (optional): explicit comma-separated rank list. `region` is normalized to `admin_region`.
- `chunk_ids` (optional): stable deterministic spatial chunk ids in `{world|regional|local}:column:row` form.
- `viewport_bucket` (optional): stable quantized viewport identity in the form `{world|regional|local}:west:south:east:north`.
- `bbox` (optional): `west,south,east,north` in WGS84. Antimeridian-wrapping requests are supported explicitly.
- `selected_location_id` (optional): explicit UUID whose polygon must be included even if it falls outside `bbox`.
- `highlighted_location_ids` (optional): comma-separated UUID list whose polygons must be included even if they fall outside `bbox`.

Validation notes:
- `geometry_detail` is removed and rejected.
- `chunk_ids`, `viewport_bucket`, and `bbox` are mutually exclusive spatial selectors.
- `chunk_ids` are normalized, deduped, and sorted canonically.
- `viewport_bucket` must align to the server-supported quantized grid for its band.
- `bbox` must contain four finite values and valid latitude ordering.
- explicit IDs must be valid UUIDs.

## PDF Range Handling

`GET /api/map/document/{document_id}/pdf` supports `Range: bytes=...` and returns proper `206` or `416` responses as applicable.

## Read-Only Guarantee

Presentation API performs no write operations.

## Search Query Length Semantics

- API input validation allows `q` length `>= 1`.
- Repository behavior returns empty `documents` and `locations` when trimmed query length is below `3`.
- Effective useful search behavior starts at 3+ trimmed characters.
