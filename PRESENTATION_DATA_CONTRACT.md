# Presentation Data Contract

## Scope

This contract includes the phase 12 implemented target fields and the phase 13 planned geometry extensions.

All IDs are UUID strings in API payloads.

## Source Tables

- `bi_documents`
- `bi_locations`
- `bi_document_locations`
- `bi_location_hierarchy`

## Location Contract

Source: `bi_locations`

Fields:

- `location_id` (UUID)
- `name` (`bi_locations.normalized_location`)
- `latitude` (float)
- `longitude` (float)
- `precision` (string|null)
- `location_rank` (string|null, planned in phase 13)
- `document_count` (int)
- `parent_location_id` (UUID|null)

Planned `location_rank` values:

- `city`
- `admin_region`
- `country`
- `continent`
- `ocean`
- `unknown`

## Document Card Contract

Source: `bi_documents` + `bi_document_locations`

Fields returned by API:

- `document_id` (UUID)
- `scp_number` (string)
- `canonical_scp_id` (string)
- `scp_url` (string)
- `location_display` (string|null)
- `pdf_url` (string|null)

Derived in frontend:

- `pdf_preview_thumbnail` (client-rendered first-page thumbnail generated from `pdf_url` via pdfjs-dist)

Notes:

- `pdf_preview_thumbnail` is not a BI table field
- `location_display` is contextual and may vary depending on the current panel result context
- `scp_number` is the canonical user-facing number shown in the card

Migration note:

Older phase 11 payload fields such as title-oriented or preview-text-oriented card shapes are not authoritative for phase 12+ document cards.

## Document-Location Link Contract

Source: `bi_document_locations` + `bi_locations`

Fields:

- `document_id` (UUID)
- `location_id` (UUID)
- `name` (string)
- `latitude` (float)
- `longitude` (float)
- `precision` (string|null)
- `location_rank` (string|null, planned in phase 13)
- `evidence_quote` (string|null)
- `mention_count` (int)

## Hierarchy Contract

Source: `bi_location_hierarchy`

Fields:

- `ancestor_location_id` (UUID)
- `descendant_location_id` (UUID)
- `depth` (int)

Depth semantics:

- `0` = self
- `1` = parent
- `2+` = upper ancestors

## Fallback Result Contract

`GET /api/map/location/{id}/documents` returns:

- `requested_location_id` (UUID)
- `resolved_location_id` (UUID|null)
- `fallback_depth` (int|null)
- `items` (`DocumentCard[]`)

Fallback semantics remain:

- `city -> region -> country`

`continent` and `ocean` are not fallback targets in phase 13.

## Search Result Contract

Source: presentation API search response

### SearchDocumentResult

- `document_id` (UUID)
- `scp_number` (string)
- `canonical_scp_id` (string)
- `scp_url` (string)
- `location_display` (string|null)
- `pdf_url` (string|null)

### SearchLocationResult

- `location_id` (UUID)
- `name` (string)
- `latitude` (float)
- `longitude` (float)
- `precision` (string|null)
- `location_rank` (string|null, planned in phase 13)
- `document_count` (int)
- `parent_location_id` (UUID|null)

## Geometry Rendering Contract

Phase 12 rendering may use either:

- point geometry from BI location coordinates
- static polygon geometry for countries and regions

Phase 13 extends static polygon geometry to:

- admin regions
- countries
- continents
- oceans

The BI contract remains coordinate-based.

Polygon geometries are not stored in the current BI contract and are supplied by static assets.

Frontend-visible geometry metadata may include:

- `geometry_kind` (`point` | `polygon`)
- `location_rank` (`city` | `admin_region` | `country` | `continent` | `ocean`)

Phase 13 geometry asset requirements:

- geometry assets should be keyed by `location_id`
- frontend polygon matching by display name alone is not authoritative
- runtime geometry generation in presentation is not allowed
- hierarchy fallback remains `city -> region -> country`

## Runtime Visualization State

The following values are UI runtime state, not persisted API fields:

- `pinned_document_id`
- `visible_linked_locations`
- `offscreen_location_count`
- `search_active`
- `pdf_modal_document_id`
