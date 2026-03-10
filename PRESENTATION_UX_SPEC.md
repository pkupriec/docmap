# PRESENTATION_UX_SPEC.md

## Layout

The interface consists of three regions:

left panel
map viewport
right panel

---

# Left Panel

Contains map controls.

Controls include:

map mode
overlay toggles
future layers

---

# Map Viewport

Primary interaction surface.

The map displays:

locations
document connections
density overlays

---

# Precision Awareness

Location precision is part of the data contract.

In MVP, precision does not require separate user controls, but it may influence:
- marker styling
- future clustering behavior
- future visual differentiation of location granularity

The frontend must preserve the precision field in its internal models.
It must not invent precision values.

# Interaction Model

Two interaction states:

hover
pinned selection

---

# UI State Machine

The MVP UI uses these states:

idle
hover_location
pinned_location
document_hover
loading
error

Transitions:

idle -> hover_location
hover_location -> idle
hover_location -> pinned_location
pinned_location -> idle
pinned_location -> document_hover
document_hover -> pinned_location
any -> loading
loading -> previous stable state
any -> error

Hover state is transient.
Pinned state is explicit and must remain stable until reset.

# Hover

When the cursor hovers over a location:

documents associated with that location appear in the right panel.

Hover state is transient.

---

# Pinned Selection

Clicking a location pins the selection.

The right panel becomes fixed.

---

# Reset Behavior

Pinned selection resets when:

user presses Esc
user clicks empty map
user presses Clear button

---

# Right Panel

Displays document cards.

Each card shows:

scp_object_id
title
preview_text

Buttons:

Open source

Opening source opens new browser tab.

---

# Document Hover

Hovering a document card highlights connections on the map.

Lines appear between the document and linked locations.

---

# Empty State

When no location is selected:

the right panel shows:

"Explore the map to discover SCP documents."

---

# Loading State

The panel shows loading indicators when data is fetched.

---

# Error State

API failures display:

"Unable to load data."

---

# Performance

Hover interaction latency must remain below:

100 ms

Initial load time target:

2 seconds

---

# Desktop First

The interface is optimized for desktop.

Mobile support is not required for MVP.

---

# Accessibility

Keyboard support:

Esc resets selection.