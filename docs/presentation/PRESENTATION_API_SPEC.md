# Presentation API Spec

Base URL in local compose: `http://localhost:8080`.

## Endpoints

- `GET /healthz`
- `GET /api/map/locations`
- `GET /api/map/boundaries?lite={bool}&rank_filter={default|all}&geometry_detail={low|full}`
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
- `GET /api/map/boundaries` defaults to `rank_filter=default` and `geometry_detail=full`.
- boundaries responses are cached in-process for 10 minutes per request shape (`lite`, `rank_filter`, `geometry_detail`).

## Boundaries Query Parameters

- `lite` (default `false`): minimal boundary properties payload.
- `rank_filter` (default `default`): includes only default map ranks (`city`, `admin_region`/`region`, `country`, `continent`, `ocean`).
- `geometry_detail` (default `full`): serves full stored geometry by default; `low` requests reduced-detail geometry.

Operator/reduced path:
- use `rank_filter=default&geometry_detail=low` (or `rank_filter=all&geometry_detail=low`) for lower-detail payloads.

## PDF Range Handling

`GET /api/map/document/{document_id}/pdf` supports `Range: bytes=...` and returns proper `206` or `416` responses as applicable.

## Read-Only Guarantee

Presentation API performs no write operations.

## Search Query Length Semantics

- API input validation allows `q` length `>= 1`.
- Repository behavior returns empty `documents` and `locations` when trimmed query length is below `3`.
- Effective useful search behavior starts at 3+ trimmed characters.
