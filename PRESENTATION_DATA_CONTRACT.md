# Presentation Data Contract

## Scope

This contract defines the fields consumed by phase 11 presentation API/UI.

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
- `document_count` (int)
- `parent_location_id` (UUID|null)

## Document Card Contract

Source: `bi_documents` + `bi_document_locations`

Fields:

- `document_id` (UUID)
- `scp_object_id` (UUID|null)
- `title` (string|null)
- `url` (string)
- `preview_text` (string|null)
- `evidence_quote` (string|null)
- `mention_count` (int)

## Document-Location Link Contract

Source: `bi_document_locations` + `bi_locations`

Fields:

- `document_id` (UUID)
- `location_id` (UUID)
- `name` (string)
- `latitude` (float)
- `longitude` (float)
- `precision` (string|null)
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

