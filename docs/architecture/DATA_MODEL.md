# Data model and ownership

Crawler-owned tables:

- `scp_objects`, `documents`
- `document_snapshots`: raw HTML, clean text, PDF, and pre-rendered WebP thumbnail

Extractor-owned tables:

- `extraction_runs`, `location_mentions`

Geocoder-owned tables:

- `geo_locations`: one geographic entity, including OSM/canonical metadata and `identity_key`
- `geo_location_aliases`: mention spelling to entity mapping
- `geo_canonical_places`, `geo_canonical_aliases`, `geo_canonical_concordances`
- `document_locations`: raw document-to-entity links

Analytics-owned tables:

- `bi_documents`, `bi_locations`, `bi_document_locations`
- `bi_location_hierarchy`, `bi_admin_boundaries`

Control-owned tables:

- `pipeline_runs`, `pipeline_stage_runs`, `pipeline_progress`, `pipeline_logs`, `pipeline_commands`

Identity rules:

- OSM concordances and canonical IDs are preferred for administrative entities.
- City aliases use a stable semantic key derived from base name, region, country, and rounded coordinates.
- Different namesakes remain separate; qualified aliases such as London variants resolve to one entity.
- Consolidation redirects raw links and aliases. Analytics rebuilds exclude unreferenced legacy entities.

Raw snapshots are durable history. Geo, BI rows, thumbnails, and PMTiles are derived and may be regenerated.
