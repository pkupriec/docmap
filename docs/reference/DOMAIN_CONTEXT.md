# Domain Context

DocMap models location mentions extracted from SCP documents.

## Core Concepts

- Document: one SCP page URL tracked in `documents`.
- Snapshot: point-in-time captured content in `document_snapshots`.
- Mention: extracted location candidate in `location_mentions`.
- Resolved location: geocoded place record in `geo_locations`.
- Document-location link: relation in `document_locations`.

## BI Perspective

Presentation and analytical queries read denormalized projections:
- `bi_documents`
- `bi_locations`
- `bi_document_locations`
- `bi_location_hierarchy`

`bi_document_locations` tracks:
- `mention_count`
- `evidence_quote`

It does not track precision/confidence fields.

## Interpretation Guidance

- Locations are inferred from text and can be ambiguous.
- Coordinates represent mapped references, not guaranteed authoritative truth.
- Canonical dictionary matching improves consistency but does not eliminate uncertainty.