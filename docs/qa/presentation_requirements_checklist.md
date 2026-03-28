# Presentation Requirements Checklist

## Scope And Authority
- Source precedence used for this QA pass:
  1. `docs/archive/legacy-agent/EXECUTION_SPEC.md`
  2. `docs/archive/legacy-agent/AGENT_RULES.md`
  3. `docs/agent/CODING_CONVENTIONS.md`
  4. `docs/agent/ANTI_PATTERNS.md`
  5. `docs/architecture/ARCHITECTURE.md`
  6. `docs/architecture/SERVICES.md`
  7. `docs/architecture/PIPELINE.md`
  8. `docs/architecture/DATA_MODEL.md`
  9. `docs/roadmap/phases/phase10_control_plane.md`
  10. `docs/roadmap/phases/phase11_presentation_layer.md`
  11. `docs/roadmap/phases/phase12_code_alignment.md`
  12. `docs/roadmap/phases/phase12_presentation_ux_iteration_1.md`
  13. `docs/roadmap/phases/phase13_map_geometry.md`
  14. `database/schema.sql`
  15. `infra/docker-compose.yml`
  16. `pyproject.toml`
  17. `main.py`
  18. Presentation/backend/frontend code and tests.

## Explicit MVP/Phase Exclusions
- `R-EXCL-001`: Presentation must remain read-only and must not write BI/operational/control tables.
- `R-EXCL-002`: Do not merge presentation runtime with control-plane runtime/UI.
- `R-EXCL-003`: Do not add pipeline-stage logic (crawl/extract/geocode) into presentation runtime.
- `R-EXCL-004`: Do not extend document fallback beyond `city -> region/admin_region -> country`.
- `R-EXCL-005`: No mobile-first redesign requirement in current scope.
- `R-EXCL-006`: No new broker/background subsystem (Redis/Kafka/Celery/NATS/etc.).

## Application Shell/Layout
- `R-SHELL-001`: Desktop-first 3-region layout: left control panel, map viewport, right document panel.
- `R-SHELL-002`: Left control panel supports collapse to a thin vertical strip while preserving visible toggle.
- `R-SHELL-003`: Left panel contains title/caption/location count/Clear control in expanded mode.
- `R-SHELL-004`: Right panel has unified search field and context-sensitive content mode.
- `R-SHELL-005`: Clear action resets pinned location, pinned document, and PDF modal state.

## Map Behavior
- `R-MAP-001`: Map loads and remains interactive while search is active.
- `R-MAP-002`: Hover location updates right panel only when search is not active.
- `R-MAP-003`: Clicking location pins location selection.
- `R-MAP-004`: Empty-map click clears pinned location and pinned document.
- `R-MAP-005`: `Esc` clears pinned location and pinned document; if PDF modal open, closes modal as well.
- `R-MAP-006`: Map emits viewport changes used to recompute visible/offscreen document links.
- `R-MAP-007`: Polygon click behavior equals point click behavior for corresponding location.

## Side Panels / Detail Panels
- `R-PANEL-001`: Right panel supports state precedence: `pdf_modal > pinned_document > document_hover > search_results > pinned_location > hover_location > idle`.
- `R-PANEL-002`: Search-active mode replaces location-driven cards with search results.
- `R-PANEL-003`: Location-driven cards show fallback depth note when fallback depth > 0.
- `R-PANEL-004`: Document card shows SCP number link, contextual location, and PDF thumbnail area.
- `R-PANEL-005`: SCP link opens source page in a new tab.
- `R-PANEL-006`: Hovering a card previews umbrella-style visible links.
- `R-PANEL-007`: Clicking a card toggles pinned-document visualization.
- `R-PANEL-008`: Clicking thumbnail opens centered PDF modal and preserves pin semantics.
- `R-PANEL-009`: Modal close button/backdrop close only modal (do not clear pin state).

## Loading / Error / Empty States
- `R-STATE-001`: Startup enters loading state and fetches locations + boundaries together.
- `R-STATE-002`: UI becomes ready only when both startup requests succeed.
- `R-STATE-003`: Startup fetch failure shows shared error message `Unable to load data.`
- `R-STATE-004`: Idle empty state text is `Explore the map to discover SCP documents.`
- `R-STATE-005`: Contextual no-results text is `No linked documents.`

## API Integration / Data Contract
- `R-API-001`: `GET /api/map/locations` returns deterministic, valid-coordinate locations with required fields.
- `R-API-002`: `GET /api/map/boundaries` returns GeoJSON `FeatureCollection` from BI boundary table.
- `R-API-003`: `GET /api/map/location/{id}/documents` returns fallback metadata and deduped document cards.
- `R-API-004`: `GET /api/map/document/{id}` returns document card payload shape.
- `R-API-005`: `GET /api/map/document/{id}/pdf` returns PDF bytes with range support and 404 behavior.
- `R-API-006`: `GET /api/map/document/{id}/locations` returns deterministic location links.
- `R-API-007`: `GET /api/map/overlays/density` returns density points.
- `R-API-008`: `GET /api/search` supports query and max limit 5; deterministic order/dedup for docs+locations.
- `R-API-009`: Search supports canonical SCP, numeric SCP, and case-insensitive location field matching.

## Refresh / Live Update Behavior
- `R-LIVE-001`: Search is debounced (~180ms) and activates at `>=3` trimmed chars.
- `R-LIVE-002`: Search focus behavior: single coordinate centers map; multiple coordinates fit bounds.
- `R-LIVE-003`: Document-only search results trigger document-location fetch for map focus.
- `R-LIVE-004`: Pinned/hovered document visible links and offscreen count recompute on viewport movement.
- `R-LIVE-005`: Pinned document survives map drag until explicit clear/reset.

## Geometry Rendering Behavior
- `R-GEO-001`: Mixed geometry model: city point-first with zoom threshold polygon option, non-city polygon ranks when available.
- `R-GEO-002`: Polygon source is analytics-owned boundary data consumed read-only by presentation.
- `R-GEO-003`: Boundary matching must prioritize stable identity (`location_id`), with current fallback support by rank+name.
- `R-GEO-004`: Missing-boundary non-city locations fall back to red points; city fallback remains blue when unselected.
- `R-GEO-005`: Cities remain coordinate-based and must not depend on runtime polygon generation.

## Control-Plane Related UI Interactions
- `R-CTRL-001`: Presentation remains separate from control-plane UI and container runtime.
- `R-CTRL-002`: Presentation can coexist in compose stack without modifying single-active-run control-plane semantics.
- `R-CTRL-003`: Presentation health endpoint `/healthz` available for runtime checks.

## Traceability Notes
- Requirement IDs are referenced by test matrix and defect log artifacts in `docs/qa/`.
