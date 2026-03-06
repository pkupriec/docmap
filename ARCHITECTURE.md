# System Architecture

Pipeline:

SCP Wiki
↓
Crawler
↓
Document Snapshots
↓
LLM Extraction
↓
Location Normalization
↓
Geocoding (Nominatim)
↓
PostgreSQL + PostGIS
↓
Analytics Tables
↓
BigQuery Export
↓
Looker Studio Map

Components:

crawler
extractor
normalizer
geocoder
analytics pipeline