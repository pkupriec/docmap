# PRESENTATION_IMPLEMENTATION_PLAN.md


The presentation layer is delivered as an independent service.

Implementation structure:

- presentation backend
- presentation frontend
- dedicated container build

The control plane remains a separate service and must not be used as the runtime host for presentation UI.

## Phase 0 — Design Hardening

Finalize documentation.

Outputs:

architecture spec
data contract
UX spec
API spec
task list

---

## Phase 1 — BI Preparation

Extend BI schema.

Tasks:

add parent_location_id
add hierarchy table
add preview_text
add evidence_quote

---

## Phase 2 — Backend

Build FastAPI service.

Tasks:

database connection
query layer
API endpoints
hierarchy fallback logic

---

## Phase 3 — Map Prototype

Implement minimal UI.

Features:

map rendering
hover interaction
pinned selection
document panel

---

## Phase 4 — Visualization

Add advanced layers:

clustering
density heatmap
map modes

---

## Phase 5 — Productionization

Tasks:

Docker container for presentation service
independent deployment configuration
logging
performance tuning
documentation refresh