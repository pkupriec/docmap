# Data Model

Entities:

scp_objects
documents
document_snapshots
extraction_runs
location_mentions
geo_locations
document_locations

Relationships:

SCP Object → Document → Snapshot → Extraction Run → Location Mentions → Geo Locations

A document can have multiple geographic links.