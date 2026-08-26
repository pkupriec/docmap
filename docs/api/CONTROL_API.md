# HTTP APIs

Control API (`:8000`):

- `GET/POST /api/runs`
- `GET /api/runs/{run_id}` plus `/stages`, `/progress`, `/logs`, and `/events`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/runs/{run_id}/retry`
- `POST /api/runs/{run_id}/stages/{stage}/retry`
- `POST /api/runs/{run_id}/stages/{stage}/resume`
- `GET /api/commands/{command_id}`

Mutation endpoints return `202` after enqueueing. The returned command status is not proof that pipeline work has completed.

Presentation API (`:8080`):

- `GET /api/map/locations`
- `GET /api/map/baked/manifest?mode=...`
- `GET /api/map/baked/archives/{version}/{mode}.pmtiles` with single HTTP byte-range support
- `GET /api/map/boundaries?selected_location_id=...&highlighted_location_ids=...`
- `GET /api/map/location/{location_id}/documents`
- `GET /api/map/document/{document_id}`
- `GET /api/map/document/{document_id}/locations`
- `GET /api/map/document/{document_id}/pdf` with database-side byte slicing
- `GET /api/map/document/{document_id}/thumbnail`
- `GET /api/map/overlays/density`
- `GET /api/search?q=...&limit=...`

Legacy XYZ, tile-index, viewport, chunk, `lite`, and bbox boundary parameters are unsupported. The manifest uses `min_zoom` and `max_zoom` and returns an `archive_url` for the selected mode.
