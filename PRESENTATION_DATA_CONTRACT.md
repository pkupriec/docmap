# PRESENTATION_DATA_CONTRACT.md

## Purpose

This document defines the data structures required by the presentation layer.

The presentation layer consumes BI tables and exposes structured responses to the frontend.

---

# Entities

Primary entities:

Document
Location
DocumentLocationLink

---

# Document

Source: bi_documents

Fields required:

document_id
scp_object_id
title
url
preview_text

Example:

{
  "document_id": 123,
  "scp_object_id": "SCP-173",
  "title": "The Sculpture",
  "url": "https://scp-wiki.wikidot.com/scp-173",
  "preview_text": "SCP-173 is constructed from concrete..."
}

---

# Location

Source: bi_locations

Fields:

location_id
name
latitude
longitude
precision
parent_location_id
document_count

Example:

{
  "location_id": 22,
  "name": "Tokyo",
  "latitude": 35.6762,
  "longitude": 139.6503,
  "precision": "city",
  "document_count": 14
}

---

# Location Hierarchy

Source: bi_location_hierarchy

Fields:

ancestor_location_id
descendant_location_id
depth

Example:

country
→ region
→ city

Used for fallback logic.

---

# Document Location Link

Source: bi_document_locations

Fields:

document_id
location_id
evidence_quote

Example:

{
  "document_id": 52,
  "location_id": 11,
  "evidence_quote": "Recovered near the outskirts of Warsaw."
}

---

# Geometry Model

MVP supports:

point geometries only.

Fields:

latitude
longitude

Future extensions:

polygon
uncertainty radius

---

# Precision Model

Precision describes the spatial granularity.

Allowed values:

continent
country
region
city
site
unknown

Precision is used for UI aggregation.

---

# Document Card Contract

Frontend requires:

scp_object_id
title
preview_text
url

Optional:

document_count
location_count

---

# Map Line Contract

Lines represent relationships between:

document ↔ location

Fields:

document_id
location_id
coordinates

---

# Density Overlay Contract

Used for heatmap layer.

Fields:

latitude
longitude
document_count