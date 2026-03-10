# PRESENTATION_API_SPEC.md

## Purpose

Defines read-only endpoints used by the frontend.

The API must be stateless.

---

# GET /api/map/locations

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

Returns documents linked to a location.

---

# GET /api/map/document/{id}/locations

Returns locations referenced by a document.

---

# GET /api/map/overlays/density

Returns density grid.

Used for heatmap layer.

---

# API Requirements

All endpoints must:

be read-only
use SQL standard queries
return deterministic results