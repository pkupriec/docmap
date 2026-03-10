# DOMAIN_CONTEXT.md

This document explains the SCP domain model used by the project.

The goal is to help AI agents understand the semantics of extracted data.

This file defines how SCP concepts map to the system data model.

---

# SCP Wiki Overview

The SCP Wiki is a collaborative fiction project.

Articles describe anomalous objects, locations, entities, and events.

Each SCP article is typically written as a containment report.

Example:

SCP-173  
SCP-096  
SCP-3008  

Each article is treated as a **document** in the system.

---

# Core Domain Entities

The project models several core entity types.

These include:

SCP objects  
organizations  
characters  
locations  
events  
anomalies

However, the **presentation layer primarily deals with two entities**:

documents  
locations

---

# Document

A document corresponds to a single SCP wiki page.

Example:

SCP-173 article.

Documents may contain:

multiple locations  
multiple characters  
multiple references

A document is not guaranteed to describe only one location.

---

# Location

Locations are geographic references extracted from text.

Examples:

cities  
regions  
countries  
specific facilities  

Locations may be:

exact  
approximate  
fictional  

The system stores coordinates when possible.

Precision indicates the confidence level.

---

# Location Mentions

Documents often reference multiple locations.

Example:

An SCP may be discovered in one place and contained in another.

Example text:

"Recovered near Warsaw and transferred to Site-19 in the United States."

This produces two location mentions.

Each mention becomes a **document-location link**.

---

# Document ↔ Location Relationship

A document may reference many locations.

A location may appear in many documents.

Therefore the system uses a **many-to-many relationship**.

This relationship is stored in:

bi_document_locations

Each link may include:

evidence_quote  
confidence  
precision

---

# Location Hierarchy

Locations may belong to larger regions.

Example:

City → Region → Country

The BI layer represents this hierarchy using:

bi_location_hierarchy

This hierarchy supports UI fallback behavior.

Example:

city documents  
→ if none exist  
region documents  
→ if none exist  
country documents

---

# Geospatial Constraints

Many SCP locations are approximate.

Coordinates should be interpreted as **representative points**, not precise measurements.

Polygons are not required in MVP.

The presentation layer uses **point geometries only**.

---

# Key Domain Principles

The system models **mentions**, not authoritative locations.

Coordinates are derived from textual references.

Data may contain uncertainty.

Visualization must preserve this uncertainty.

---

# Important Implication for AI Agents

Agents must not assume:

that each SCP has a single location  
that locations are exact  
that geographic hierarchy is perfect  

Extraction must preserve ambiguity where it exists.