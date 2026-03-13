# Service Boundaries

This document is authoritative for module ownership and write boundaries.

## Ownership Matrix

- `crawler` (`implemented`): `scp_objects`, `documents`, `document_snapshots`
- `extractor` (`implemented`): `extraction_runs`, `location_mentions`
- `geocoder` (`implemented`): `geo_locations`, `document_locations`
- `analytics` (`implemented`): `bi_documents`, `bi_locations`, `bi_document_locations`, `bi_location_hierarchy`
- `presentation` (`implemented`): reads `bi_documents`, `bi_locations`, `bi_document_locations`, `bi_location_hierarchy`; writes nothing
- `control plane` (`implemented`): `pipeline_runs`, `pipeline_stage_runs`, `pipeline_progress`, `pipeline_logs`, `pipeline_commands`

## 1) Crawler

Files: `services/crawler/*`

Responsibilities (`implemented`):
- canonical URL generation
- HTML fetch with retry/backoff and throttling
- clean text extraction
- PDF rendering to `pdf_blob`
- snapshot create-if-changed
- PDF backfill if snapshot exists but PDF missing

Notable limits:
- `partial`: content extraction heuristics are rule-based and can miss edge cases

## 2) Extractor

Files: `services/extractor/*`

Responsibilities (`implemented`):
- build prompt from snapshot clean text
- call Ollama generation endpoint
- parse and validate JSON response
- persist extraction run + mentions

Behavior:
- retries malformed/transient failures
- supports callback + stop boundary control
- model/runtime tuning is configurable via env (`EXTRACTOR_MODEL`, `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_THINK_LEVEL`, `OLLAMA_NUM_PREDICT`)
- prompt contains anti-hallucination, canonical normalization, and deduplication guidance

## 3) Geocoder

Files: `services/geocoder/*`

Responsibilities (`implemented`):
- normalize mentions (in-place updates)
- geocode unresolved mentions via Nominatim
- cache by normalized name
- create `document_locations` links

Behavior:
- unresolved/invalid items are logged and skipped
- supports callback + stop boundary control
- Nominatim access is rate-limit aware (request throttling + 429 backoff + query fallbacks)
- transaction unit is one mention: each mention is committed independently (rollback only for failed item)

## 4) Analytics

Files: `services/analytics/service.py`

Responsibilities (`implemented`):
- truncate/rebuild BI tables from operational data
- optional step callback with `start_index` support

Responsibilities (`extended in phase 12`):
- build deterministic static administrative geometry assets for presentation mixed-geometry rendering
- source geometry build targets from BI locations (`country`, `region`) after BI rebuild is complete
- publish generated asset for presentation runtime consumption (for example `services/presentation/frontend/src/assets/admin_boundaries.geojson`)
- produce deterministic ordering and stable output for identical BI input

Responsibilities (`planned in phase 13`):
- extend geometry asset generation to support `continent` and `ocean`
- match generated geometry to presentation locations by stable identity instead of display-name-only matching
- emit coverage diagnostics by geometry rank

Constraints:
- analytics geometry build must not mutate BI or operational tables
- presentation remains read-only and must not perform runtime geometry generation

## 5) BigQuery Export

Files: `services/analytics/bigquery_exporter.py`

Responsibilities (`implemented`):
- dataset ensure
- table export in `full` or `incremental` mode
- retry per table

Notable limits:
- `partial`: requires external credentials/permissions; no in-app secret management

## 6) Control Plane

Files: `services/control/*`

Responsibilities (`implemented`):
- API command enqueueing
- command polling/execution
- run/stage state transitions
- logs/progress emission
- SSE event stream

Notable limits:
- `partial`: no authentication/authorization layer
- `partial`: no dedicated external queue/broker

## 7) Presentation

Files:
- `services/presentation/backend/*`
- `services/presentation/frontend/*`
- runtime entrypoint: `main_presentation.py`

Responsibilities (`implemented`):
- expose read-only API for map/location/document exploration
- render interactive spatial UI
- provide location-to-document and document-to-location navigation
- support hierarchy fallback (`city -> region -> country`)
- support hover and pinned location selection behavior

Responsibilities (`extended in phase 12`):
- provide API-backed search
- support redesigned document cards
- support PDF thumbnail + modal interactions
- support pinned document visualization
- support mixed geometry rendering for countries/regions with city points

Responsibilities (`planned in phase 13`):
- render `admin_region`, `country`, `continent`, and `ocean` as real polygon geometry when available
- preserve `city` as point rendering
- consume geometry assets keyed by stable location identity
- preserve current hierarchy fallback without extending it to `continent` or `ocean`

Behavior:
- reads BI tables only
- must not write to any operational or BI table
- must use portable SQL suitable for PostgreSQL and later BI portability targets
- must not call crawler, extractor, or geocoder logic directly

Phase 12 may require coordinated updates to:

- backend response schemas
- repository/query logic
- API handlers
- frontend state/rendering
- automated tests

These updates remain within the presentation service boundary and do not violate the read-only architectural role.

Notable limits:
- `implemented`: phase 11 MVP started with point geometries only
- `extended in phase 12`: mixed geometry is allowed for country/region polygons with city points
- `planned`: phase 13 broadens geometry coverage and identity matching for non-city polygons
- `extended in phase 12`: API-backed search is part of the presentation layer
- `implemented`: desktop-first UX (mobile is out of scope for the current phase)
