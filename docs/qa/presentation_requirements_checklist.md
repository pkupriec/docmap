# Presentation Requirements Checklist

## Scope And Authority
- Source precedence for the current presentation QA pass:
  1. `docs/presentation/PRESENTATION_UX_SPEC.md`
  2. `docs/presentation/PRESENTATION_API_SPEC.md`
  3. `docs/presentation/PRESENTATION_DATA_CONTRACT.md`
  4. `docs/presentation/PRESENTATION_ARCHITECTURE.md`
  5. `docs/architecture/ARCHITECTURE.md`
  6. `docs/architecture/SERVICES.md`
  7. `docs/architecture/DATA_MODEL.md`
  8. `database/schema.sql`
  9. `infra/docker-compose.yml`
  10. Presentation backend/frontend code and tests

## Explicit Exclusions
- `R-EXCL-001`: Presentation must remain read-only and must not write BI, operational, or control-plane tables.
- `R-EXCL-002`: Presentation remains a separate runtime from the control-plane UI/runtime.
- `R-EXCL-003`: Presentation must not run pipeline-stage logic directly.
- `R-EXCL-004`: Current scope is desktop-first, not a mobile-first redesign.

## Application Shell And Layout
- `R-SHELL-001`: Desktop-first 3-region layout: left control panel, map viewport, right document panel.
- `R-SHELL-002`: Left panel supports collapse to a thin strip while preserving a visible toggle.
- `R-SHELL-003`: Expanded left panel shows title, caption, location count, and `Clear`.
- `R-SHELL-004`: Collapsed left panel exposes compact quick actions for search focus and clear.
- `R-SHELL-005`: Right panel includes a unified search field and context-sensitive content.
- `R-SHELL-006`: Map viewport displays legend, zoom controls, and visible zoom-level widget.

## Interaction State And Selection
- `R-STATE-UI-001`: Right panel state precedence is `pdf_modal > pinned_document > document_hover > search_results > pinned_location > hover_location > idle`.
- `R-STATE-UI-002`: Clicking a location pins the selection.
- `R-STATE-UI-003`: Empty-map click clears pinned location and pinned document.
- `R-STATE-UI-004`: `Clear` clears pinned location, pinned document, and PDF modal state.
- `R-STATE-UI-005`: `Esc` clears pinned location and pinned document; if PDF modal is open it also closes the modal.
- `R-STATE-UI-006`: Search-active mode keeps map interaction enabled but prevents hover/pin from replacing search-driven right-panel content.
- `R-STATE-UI-007`: Visible mode summary reflects the active state and selected-location summary pill updates with current selection.
- `R-STATE-UI-008`: Pinned location remains selected while the map is dragged or hovered elsewhere until an explicit reset source is used.

## Startup, Loading, Error, Empty States
- `R-STARTUP-001`: Frontend starts in `loading`.
- `R-STARTUP-002`: Locations are fetched first and are the readiness gate for the UI.
- `R-STARTUP-003`: Boundaries are not fetched until the map reports a viewport, and then hydrate overlays in the background.
- `R-STARTUP-004`: Startup failure shows `Unable to load locations.`
- `R-STARTUP-005`: Boundaries-only failure is non-fatal and shows `Boundaries unavailable. Showing location points only.`
- `R-STARTUP-006`: While waiting for the first viewport the UI shows `Waiting for map viewport before loading boundaries...`, and later shows `Loading boundaries in background...` during scoped refreshes.
- `R-EMPTY-001`: Idle right-panel text is `Explore the map to discover SCP documents.`
- `R-EMPTY-002`: Contextual no-results text is `No linked documents.`

## Search Behavior
- `R-SEARCH-001`: Search activates at `>=3` trimmed characters and is debounced by about `180 ms`.
- `R-SEARCH-002`: Search uses API-backed results and shows a result summary in the right panel.
- `R-SEARCH-003`: Search supports canonical SCP, numeric SCP, and case-insensitive location matching.
- `R-SEARCH-004`: If search returns locations, the map centers/fits those locations.
- `R-SEARCH-005`: If search returns only documents, the frontend fetches linked document locations and fits deduplicated coordinates.
- `R-SEARCH-006`: Search location results render as clickable chips that pin the selected location without replacing the search panel content.
- `R-SEARCH-007`: Short queries below the useful threshold produce no active search results in the UI.
- `R-SEARCH-008`: Search request limit is capped at 5 results per category.

## Document Panel And Visualization
- `R-PANEL-001`: Location-driven document responses show scope metadata and alias-depth note when `fallback_depth > 0`.
- `R-PANEL-002`: Document cards show SCP number link, contextual location, and PDF thumbnail or `No PDF preview`.
- `R-PANEL-003`: SCP number link opens the SCP source page in a new tab.
- `R-PANEL-004`: Hovering a document card previews umbrella-style visible links.
- `R-PANEL-005`: Clicking a document card toggles pinned-document visualization.
- `R-PANEL-006`: Pinned document visualization survives map drag and viewport updates.
- `R-PANEL-007`: Offscreen linked-location count updates as the viewport changes.
- `R-PANEL-008`: When a document visualization is active, the right panel exposes declutter-link controls.
- `R-PANEL-009`: Clicking a thumbnail pins the document and opens a centered PDF modal.
- `R-PANEL-010`: Close button and backdrop click close only the modal; `Esc` also clears pinned state.
- `R-PANEL-011`: Clicking a different document card while a PDF modal is open closes the current modal.
- `R-PANEL-012`: Location-driven results support incremental pagination through `Load more`.

## Geometry Rendering
- `R-GEO-001`: Mixed geometry model: cities render as points by default, and as polygons only when a matching boundary exists and zoom is `>= 3.2`.
- `R-GEO-002`: `admin_region`, `country`, `continent`, `ocean`, `national_park`, and `desert` render as polygons when matching boundaries exist, otherwise as points.
- `R-GEO-003`: Boundary matching first tries `location_id`, then falls back to rank-aware alias/name matching.
- `R-GEO-004`: Boundary-unavailable non-city points use a neutral blue fallback style rather than issue-red.
- `R-GEO-005`: City fallback points remain blue when unselected.
- `R-GEO-006`: Polygon click behavior matches click behavior for the corresponding location point.
- `R-GEO-007`: Overlapping picks should prefer the stronger candidate deterministically, favoring locations with documents.
- `R-GEO-008`: Viewport-driven boundaries requests are scoped by stable chunk identities and explicit `ranks`, with explicit selected/highlighted IDs included outside the viewport scope.
- `R-GEO-009`: Presentation serves full stored geometry only and does not expose a reduced-detail geometry mode.
- `R-GEO-010`: Selection/highlight changes must not force a full viewport boundary reload; explicit polygon loading is additive and merged by `location_id`.
- `R-GEO-011`: Nearby pan/zoom should fetch only newly intersecting chunks while reusing overlapping loaded chunks.

## API Integration And Data Contract
- `R-API-001`: `GET /api/map/locations` returns deterministic, valid-coordinate location rows with required fields.
- `R-API-002`: `GET /api/map/boundaries` returns GeoJSON `FeatureCollection` from analytics-owned boundary data and supports `lite`, `rank_filter`, `ranks`, `chunk_ids|viewport_bucket|bbox`, `selected_location_id`, and `highlighted_location_ids`.
- `R-API-003`: `GET /api/map/location/{id}/documents` returns pagination plus scope metadata and deduped document cards.
- `R-API-004`: `GET /api/map/document/{id}` returns document-card payload shape.
- `R-API-005`: `GET /api/map/document/{id}/pdf` returns PDF bytes with range support and not-found behavior.
- `R-API-006`: `GET /api/map/document/{id}/locations` returns deterministic location links.
- `R-API-007`: `GET /api/search` returns deterministic deduped document and location results.
- `R-API-008`: `GET /api/map/overlays/density` returns density points.
- `R-API-009`: Unresolved `GET /api/map/location/{id}/documents` requests return `200` with null/empty scoped payload rather than `404`.
- `R-API-010`: Missing document card and PDF resources return `404 {"error":"not_found"}`.
- `R-API-011`: Invalid PDF byte ranges return `416` with appropriate `Content-Range`.
- `R-API-012`: Search API accepts `q` length `>=1`, but trimmed queries below 3 return empty results from repository behavior.
- `R-API-013`: Boundaries responses are cached in-process per canonical request shape, preferring stable `chunk_ids` identity over raw float viewport churn when available.

## Pipeline-Derived Data Anomalies
- `R-DATA-001`: Presentation can legitimately show stale location, hierarchy, or geometry behavior when upstream geocoder fixes have not yet been followed by an analytics rebuild.
- `R-DATA-002`: Geocoder fixes do not retroactively rewrite already persisted bad `geo_locations` rows unless the affected rows are re-geocoded.
- `R-DATA-003`: `process_unprocessed_only` runs may leave existing bad cached geo identities untouched because refresh options are ignored in that mode.
- `R-DATA-004`: Geocode resume from mid-stage can skip canonical refresh, so canonical-dictionary changes may not be reflected until a full stage restart.
- `R-DATA-005`: Duplicate semantic locations can exist as separate rows (for example alias/language variants or old-vs-new normalized names), producing colocated markers or search/click mismatches.
- `R-DATA-006`: A geocoded location without matched boundary geometry is not inherently bad data; it may be a legitimate point-only location with missing upstream coverage.
- `R-DATA-007`: Non-city document aggregation depends on `bi_location_hierarchy`, not loose country/region-name matching.
- `R-DATA-008`: `bi_document_locations` is a rolled-up analytics projection that stores mention counts and evidence quote but not full confidence/precision context.
- `R-DATA-009`: `bi_documents.latest_snapshot_id` can be absent even when document/location links exist, causing missing PDF preview or PDF endpoint `404` independently of map linkage correctness.
- `R-DATA-010`: Presentation filters out invalid or non-finite coordinates, so upstream rows can exist without appearing on the map.

## Architecture And Runtime Separation
- `R-ARCH-001`: Presentation consumes BI/runtime data read-only.
- `R-ARCH-002`: Presentation startup and rendering must not generate runtime geometry or other write-side side effects.
- `R-ARCH-003`: Presentation exposes `/healthz` independently of the control plane.

## Traceability Notes
- Requirement IDs are referenced by the presentation test matrix and related QA artifacts in `docs/qa/`.
