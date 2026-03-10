# PRESENTATION_API_SPEC.md

## Purpose

Defines read-only endpoints used by the frontend.

The API must be stateless.

---

# GET /api/map/locations

Schema: LocationResponse

Fields:
- location_id
- name
- latitude
- longitude
- precision
- document_count
- parent_location_id (optional in response if needed by client)

Returns all visible locations.

Response:

[
  {
    "location_id": 1,
    "name": "Paris",
    "latitude": 48.8566,
    "longitude": 2.3522,
    "precision": "city",
    "document_count": 5
  }
]

---

# GET /api/map/location/{id}/documents

Schema: DocumentCard

Fields:
- document_id
- scp_object_id
- title
- url
- preview_text
- evidence_quote (optional)

Returns documents linked to a location.

---

# GET /api/map/document/{id}/locations

Schema: DocumentLocationLink

Fields:
- document_id
- location_id
- latitude
- longitude
- precision
- evidence_quote (optional)

Returns locations referenced by a document.

---

# GET /api/map/overlays/density

Schema: DensityPoint

Fields:
- latitude
- longitude
- document_count

Returns density grid.

Used for heatmap layer.

---

# API Requirements

All endpoints must:

be read-only
use SQL standard queries
return deterministic results
All SQL used by API endpoints must follow portable SQL rules.

Queries should remain compatible with:
- PostgreSQL
- BigQuery
- DuckDB

Avoid PostGIS-only API query semantics.
Return coordinates as latitude/longitude fields in API responses.