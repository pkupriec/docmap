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

## Control Plane (Phase 10)

- Backend API: FastAPI app in `main.py` with endpoints under `/api` (see `docs/CONTROL_API.openapi.yaml`).
- Control schema: `database/control_plane.sql` (mounted in `infra/docker-compose.yml`).
- Operator UI: React app in `ui/` (Runs List, Run Details, Live Logs).
