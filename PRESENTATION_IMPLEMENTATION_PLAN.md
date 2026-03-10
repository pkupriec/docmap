# Presentation Implementation Plan

## Status

Phase 11 MVP is implemented with dedicated backend/frontend module trees and a separate container runtime.

## Delivered Structure

- backend: `services/presentation/backend/*`
- frontend: `services/presentation/frontend/*`
- runtime entrypoint: `main_presentation.py`
- container build: `Dockerfile.presentation`
- compose service: `presentation` in `infra/docker-compose.yml`

## Delivered BI Extensions

- `bi_documents.preview_text`
- `bi_locations.parent_location_id`
- `bi_document_locations.evidence_quote`
- `bi_location_hierarchy`

## Delivered API

- `GET /api/map/locations`
- `GET /api/map/location/{location_id}/documents`
- `GET /api/map/document/{document_id}/locations`
- `GET /api/map/overlays/density`
- `GET /healthz`

## Delivered UX

- map-first desktop layout
- hover preview
- pinned selection on click
- reset via `Esc`, empty-map click, and `Clear`
- document cards with `preview_text`
- source links open in a new browser tab

## Remaining Planned Enhancements

- richer map modes and clustering tuning
- additional visual layers beyond density points
- production deployment hardening

