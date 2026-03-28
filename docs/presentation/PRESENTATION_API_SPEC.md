# Presentation API Spec

Base URL in local compose: `http://localhost:8080`.

## Endpoints

- `GET /healthz`
- `GET /api/map/locations`
- `GET /api/map/boundaries?lite={bool}`
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

For not-found map/document resources:

```json
{"error": "not_found"}
```

## PDF Range Handling

`GET /api/map/document/{document_id}/pdf` supports `Range: bytes=...` and returns proper `206` or `416` responses as applicable.

## Read-Only Guarantee

Presentation API performs no write operations.