# Service Boundaries Summary

Write ownership:

- crawler -> `scp_objects`, `documents`, `document_snapshots`
- extractor -> `extraction_runs`, `location_mentions`
- geocoder -> `geo_locations`, `document_locations`
- analytics -> `bi_*`
- control plane -> `pipeline_*`
- presentation -> no writes

Hard boundaries:

- crawler does not extract or geocode
- extractor does not geocode
- analytics does not mutate operational facts
- presentation reads BI/runtime projections only and does not call pipeline stages directly

Read [SERVICES.md](D:/Sources/docmap/SERVICES.md) for the full ownership matrix and subsystem responsibilities.
