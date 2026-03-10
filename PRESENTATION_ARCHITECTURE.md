# PRESENTATION_ARCHITECTURE.md

## Purpose

The presentation layer provides an interactive spatial interface for exploring SCP knowledge extracted by the processing pipeline.

The interface allows users to explore SCP documents and entities through geographic navigation.

The presentation layer is a **read-only consumer** of the structured data produced by the processing pipeline.

It does not perform extraction, normalization, or geocoding.

---

# Architectural Position

System layers:

crawler
→ extractor
→ geocoder
→ pipeline
→ database (operational tables)
→ BI projections (bi_* tables)
→ presentation layer

The presentation layer reads **only BI tables**.

---

# Responsibilities

The presentation layer is responsible for:

- rendering an interactive geographic interface
- presenting SCP documents linked to locations
- supporting spatial navigation
- visualizing relationships between documents and locations
- exposing a user-facing UI and API

The presentation layer must NOT:

- modify operational tables
- modify BI tables
- perform data extraction
- perform entity normalization
- perform geocoding

---

# Service Model

The presentation layer is implemented as a standalone service.

Deployment model:

containerized service

Example deployment targets:

- GCP Cloud Run
- GCE VM
- Kubernetes

---

# Data Source

The presentation layer reads from:

bi_documents
bi_locations
bi_document_locations
bi_location_hierarchy

These tables are considered **stable BI projections**.

The presentation layer must treat them as read-only.

---

# SQL Requirements

All queries must follow standard SQL compatible with:

PostgreSQL
BigQuery
DuckDB

Avoid vendor-specific extensions.

Spatial coordinates must be represented as:

latitude
longitude

Not PostGIS geometry types in the API layer.

---

# Data Flow

Database (BI tables)
→ Presentation API
→ Frontend UI
→ Map rendering engine

---

# Technology Stack

Frontend:

Next.js
TypeScript
MapLibre GL JS
deck.gl

Backend:

Python
FastAPI

Database access:

read-only SQL queries

---

# Service Boundaries

The presentation service does not interact with:

crawler
extractor
geocoder

It only consumes their results.

---

# Determinism

The presentation layer must not alter the meaning of extracted data.

The UI is a visualization of existing structured data.

All queries must produce deterministic results given identical BI tables.

---

# Extensibility

The architecture must allow future additions:

polygon geometries
density overlays
weather layers
custom visual layers
search

These features must not require architectural changes.

---

# Non Goals

The presentation layer will not:

edit SCP data
store user data
implement authentication
run multiple processing pipelines

These capabilities are outside scope.