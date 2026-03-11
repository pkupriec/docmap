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

## GET `/api/search`

Performs deterministic presentation search for:

- SCP canonical numbers
- numeric SCP queries
- location display fields

Query parameters:

- `q`: string, required
- `limit`: integer, optional, default `5`, maximum `5`

Activation rule:

- frontend triggers this endpoint only after input length >= 3

Response:

json
{
  "query": "scp-104",
  "documents": [
    {
      "document_id": "uuid",
      "scp_number": "SCP-1041",
      "canonical_scp_id": "scp-1041",
      "scp_url": "https://scp-wiki.wikidot.com/scp-1041",
      "location_display": "Vladimir, Russia",
      "pdf_url": "/snapshots/scp-1041.pdf"
    }
  ],
  "locations": [
    {
      "location_id": "uuid",
      "name": "Vladimir, Russia",
      "latitude": 56.129,
      "longitude": 40.407,
      "precision": "city",
      "document_count": 12,
      "parent_location_id": "uuid-or-null"
    }
  ]
}

Ordering rules:

- document results must be deterministic
- exact canonical SCP matches rank above numeric-only matches
- numeric-only SCP matches rank above location-name contains matches
- location results must be deterministically ordered by relevance, then stable secondary keys

Deduplication rules:

- duplicate documents must not appear multiple times
- duplicate locations must not appear multiple times
- nested location matches must remain distinct entities, but map-fit logic must deduplicate coordinates when computing viewport fit


## Search Result Viewport Behavior

Viewport fitting is a frontend behavior driven by search response content.

Rules:

- if exactly one location is returned, the map centers on that location
- if multiple locations are returned, the map fits the bounding box of unique result coordinates
- if documents are returned without explicit location matches, the frontend may resolve associated locations through existing document/location endpoints

## GET `/api/map/document/{document_id}`

Returns a single document card payload suitable for:
- right-panel rendering
- modal coordination
- future deep-link support

Response shape must be aligned with the document card contract in `PRESENTATION_DATA_CONTRACT.md`.

At minimum, the endpoint must be able to return:

- document_id
- scp_number
- canonical_scp_id
- scp_url
- location_display
- pdf_url

Backward compatibility note:

Phase 11 endpoints may remain available during phase 12, but payloads used by the updated document cards may be extended or revised to match `PRESENTATION_DATA_CONTRACT.md`.

The implementation must prioritize the phase 12 document card contract over obsolete phase 11 card field names.

## Static Geometry Assets

Phase 12 mixed geometry uses static administrative boundary assets.

These assets are not API-mutated resources.

Rules:

- countries and regions may be loaded from static GeoJSON or equivalent static frontend-served assets
- the presentation API remains read-only
- the geometry asset set must be deterministic for a given build/runtime state

Backward compatibility note:

Phase 11 endpoints may remain available during phase 12, but payloads used by the updated document cards may be extended or revised to match `PRESENTATION_DATA_CONTRACT.md`.

The implementation must prioritize the phase 12 document card contract over obsolete phase 11 card field names.

Implementation note:

If existing backend handlers, schemas, or tests do not match this API spec, they must be updated during phase 12 implementation.