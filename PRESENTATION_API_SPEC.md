# Presentation API Spec

## Scope

Read-only API for presentation map UI.

Base paths:

- map endpoints: `/api/map/*`
- health: `/healthz`

## GET `/api/map/locations`

Returns all point locations from `bi_locations` with deterministic ordering.

Response: `Location[]`

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

Fallback:

- direct location first
- if empty: nearest ancestor depth with documents (`city -> region -> country`)

## GET `/api/map/document/{document_id}/locations`

Returns linked locations for a document.

Path parameter:

- `document_id` UUID

Response: `DocumentLocationLink[]`

## GET `/api/map/overlays/density`

Returns density points from `bi_locations`.

Response: `DensityPoint[]`

## Determinism and Read-Only Rules

- API performs `SELECT` queries only.
- Responses are deterministically ordered.
- API does not call crawler/extractor/geocoder services.

