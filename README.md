# DocMap

DocMap is a system that extracts geographic references from SCP Wiki documents and visualizes them on a map.

The system processes SCP documents, extracts geographic mentions using LLMs, geocodes them, and publishes the results for visualization in Google Looker Studio.

Main pipeline:

SCP Wiki → Crawler → LLM Extraction → Geocoding → PostGIS → BigQuery → Looker

The project is designed for AI-assisted development using coding agents.

See:

PROJECT.md
ARCHITECTURE.md
DATA_MODEL.md
PIPELINE.md