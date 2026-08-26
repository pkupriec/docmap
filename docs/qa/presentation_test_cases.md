# Presentation Test Cases Matrix

| test_id | requirement_reference | feature_area | preconditions | steps | expected_result | automation_status |
|---|---|---|---|---|---|---|
| TC-001 | R-SHELL-001,R-SHELL-003,R-SHELL-005,R-SHELL-006,R-EXCL-004 | shell/layout | presentation service running | Open `/` | 3-region desktop-first layout renders with expanded left-panel title/caption/location count/Clear, search field, map legend, zoom controls, and visible zoom-level widget | manual+e2e |
| TC-002 | R-SHELL-002,R-SHELL-004 | shell/collapse | app loaded | Click collapse toggle, then use collapsed quick actions | Left panel collapses to thin strip, toggle remains visible, search-focus and clear quick actions work | manual+e2e |
| TC-003 | R-STATE-UI-002,R-STATE-UI-004 | shell/reset | app loaded with pinned location, pinned doc, and open modal | Click `Clear` | location pin can be established first, then `Clear` removes pinned location and document and closes the modal | manual+e2e |
| TC-004 | R-STARTUP-001,R-STARTUP-002,R-STARTUP-003 | startup/ready | backend reachable | Hard refresh page | UI enters loading, becomes ready after locations load, sends no boundary request before the first viewport, and then hydrates scoped boundaries in the background | manual+e2e |
| TC-005 | R-STARTUP-004 | startup/error | force locations API failure | Load page | `Unable to load locations.` shown | manual |
| TC-006 | R-STARTUP-005,R-STARTUP-006 | startup/boundaries degradation | force boundaries API failure or slowdown while locations succeed | Load page | UI remains usable after locations load; before the first viewport it shows the waiting-for-viewport note, during scoped refresh it shows the background-loading note, and on failure it shows the non-fatal boundaries warning | manual+e2e |
| TC-007 | R-STATE-UI-001,R-STATE-UI-007,R-STATE-UI-008 | state/mode summary | app loaded with selectable location and document data | hover location, pin location, hover document, pin document, open modal | mode pill and selection summary reflect current precedence order; pinned location persists until explicit reset | manual+e2e |
| TC-008 | R-EMPTY-001,R-EMPTY-002 | empty states | app loaded with no active search and no selected location; use a location or search that has zero docs | observe idle panel, then create a no-results context | idle state shows `Explore the map to discover SCP documents.` and contextual empty state shows `No linked documents.` | manual+e2e |
| TC-009 | R-API-001 | API locations | test DB fixture | GET `/api/map/locations` | deterministic rows, valid coordinates, and required fields present | automated |
| TC-010 | R-API-002,R-GEO-008,R-GEO-009,R-GEO-010,R-GEO-011,R-API-013 | API boundaries | test DB fixture with boundary rows of different ranks and envelopes | GET `/api/map/boundaries` variants across `chunk_ids`, `viewport_bucket`, `bbox`, `ranks`, selected/highlighted IDs, and repeated canonical-equivalent requests | viewport/rank filters are parsed strictly, stable chunk identities are normalized, explicit IDs are included outside the viewport, full geometry remains canonical, duplicate `location_id` rows are suppressed, and repeated identical request shapes reuse cached payloads | automated |
| TC-040 | R-GEO-010,R-GEO-011,R-STARTUP-006 | viewport vs explicit loading | presentation app running with browser devtools available | load the map, establish a viewport chunk set, pan to an overlapping viewport, then change selection/highlight without moving the viewport | pan requests only newly needed chunks, overlapping chunks are reused, selection/highlight triggers only additive explicit polygon fetches, current viewport polygons remain visible during refresh, and no full viewport chunk reload fires solely because focus state changed | manual+e2e |
| TC-011 | R-API-003,R-PANEL-001 | location documents API | hierarchy fixture with fallback metadata | GET `/api/map/location/{id}/documents` | scope metadata present, cards deduped, and alias-depth note available when `fallback_depth > 0` | automated |
| TC-012 | R-API-009 | unresolved location documents API | fixture where requested location cannot resolve | GET `/api/map/location/{id}/documents` for unresolved location | returns `200` with `resolved_location_id=null`, zero counts, and empty `items` | automated |
| TC-013 | R-API-004,R-API-010 | API document card | fixture with existing and missing docs | GET `/api/map/document/{id}` for existing and missing IDs | valid document returns required payload; missing document returns `404 {"error":"not_found"}` | automated |
| TC-014 | R-API-005,R-API-010,R-API-011 | API PDF | fixture with `pdf_blob` | GET `/api/map/document/{id}/pdf`, valid `Range`, invalid `Range`, and missing doc | full response, partial range, `416` for invalid range, and `404 {"error":"not_found"}` for missing work | automated |
| TC-015 | R-API-006 | API doc locations | fixture with mention counts | GET `/api/map/document/{id}/locations` | deterministic ordering and payload fields returned | automated |
| TC-016 | R-API-007,R-SEARCH-003,R-SEARCH-008,R-API-012 | API search | fixture with matching docs and locations | GET `/api/search` with rich query, short trimmed query, and high limit attempt | deterministic deduped results, max 5 per category, and short-query requests yield empty arrays from repository behavior | automated |
| TC-017 | R-SEARCH-001,R-SEARCH-007 | search activation | app loaded | Type `<3` trimmed chars, then `3+` chars | search remains inactive below threshold and activates after `3+` trimmed chars with debounce | manual+e2e |
| TC-018 | R-STATE-UI-003,R-STATE-UI-006,R-SEARCH-002 | search/panel isolation | search active | hover and click map locations, then click empty map | map remains interactive, selected map highlight updates, right panel stays search-driven with result summary, and empty-map click clears pinned state | manual+e2e |
| TC-019 | R-SEARCH-004,R-SEARCH-005,R-SEARCH-006 | search/map sync | app loaded with known search hits | run location-hit search and doc-only search, then click a location chip | location-hit search centers/fits matching locations; doc-only search fetches linked coordinates; clicking a chip pins the location while search panel remains active | manual+e2e |
| TC-020 | R-PANEL-002,R-PANEL-003 | document card | location/search results available | inspect cards and click SCP link | SCP number, contextual location, and thumbnail state render; SCP link opens in a new tab | manual+e2e |
| TC-021 | R-PANEL-004,R-PANEL-005,R-PANEL-006,R-PANEL-007 | document visualization | cards available | hover then click card, drag map, and move viewport | umbrella links render on hover and pin, pinned visualization survives drag, and offscreen count updates with viewport changes | manual+e2e |
| TC-022 | R-PANEL-008 | visualization controls | active document visualization with many visible links | toggle declutter checkbox | visible link rendering switches between decluttered and full sets, and hidden visible-link count updates when applicable | manual+e2e |
| TC-023 | R-PANEL-009,R-PANEL-010,R-PANEL-011 | PDF modal | card with `pdf_url` | click thumbnail, close by button, close by backdrop, press `Esc`, then click a different card while modal is open | modal opens centered in iframe, button/backdrop close only modal, `Esc` also clears pinned state, and clicking another card closes the current modal | manual+e2e |
| TC-024 | R-STATE-UI-005 | keyboard reset | pinned location/doc with optional modal | press `Esc` | pinned state clears, and modal closes if open | manual+e2e |
| TC-025 | R-GEO-001,R-GEO-002,R-GEO-003 | geometry matching | fixtures with city, region, country, ocean, national park, desert, and alias cases | interact at multiple zoom levels and compare matched boundaries | city threshold behavior and non-city polygon behavior match current rank rules, including `national_park` and `desert`; matching prefers `location_id` then rank-aware alias matching | manual+e2e |
| TC-026 | R-GEO-004,R-GEO-005 | geometry fallback styling | fixture with missing-boundary city and missing-boundary non-city locations | inspect fallback markers | boundary-unavailable non-city point uses neutral blue fallback styling; city fallback remains blue when unselected | manual+e2e |
| TC-027 | R-GEO-006,R-GEO-007 | geometry interaction | fixture with overlapping points/polygons and colocated aliases | hover and click overlapping map targets | polygon click matches point click semantics, and overlapping picks prefer the stronger deterministic candidate, favoring docs-backed locations | manual+e2e |
| TC-028 | R-PANEL-012 | location document pagination | selected location has more than one page of docs | click `Load more` | next page appends deduped cards and button disables while loading | manual+e2e |
| TC-029 | R-API-008 | overlays API | fixture with density points | GET `/api/map/overlays/density` | density point payload returned with valid coordinates and counts | automated |
| TC-030 | R-ARCH-001,R-ARCH-002,R-EXCL-001,R-EXCL-003 | architecture guard | runtime running | inspect network/backend behavior during render | presentation performs read-only fetches and does not trigger write-side geometry generation or pipeline behavior | automated+manual |
| TC-031 | R-ARCH-003,R-EXCL-002 | service separation | docker compose stack | start presentation and check `/healthz` | presentation runs independently from control plane and health endpoint returns ok | manual+automated |
| TC-032 | R-DATA-001,R-DATA-002 | stale geocode vs analytics state | fixture or live case where geocoder logic has been fixed but persisted rows are not yet rebuilt | compare current presentation/API result with known corrected upstream logic | QA notes the issue as persisted-data state when wrong identity remains until re-geocode and analytics rebuild; do not misclassify as frontend-only | manual+diagnostic |
| TC-033 | R-DATA-003,R-DATA-004 | pipeline option anomaly | run geocode with `process_unprocessed_only` or resume mid-stage after canonical/input changes | inspect resulting presentation data after run | QA expects previously cached bad identities or old canonical behavior may remain, and flags required rerun mode before treating as UI defect | manual+diagnostic |
| TC-034 | R-DATA-005,R-GEO-007 | duplicate semantic location anomaly | fixture or live case with alias/language duplicates at same or near-identical coordinates | search, hover, and click overlapping semantic peers | QA verifies overlap handling prefers stronger docs-backed peer but also records upstream duplicate-row anomaly for geocoder/canonical follow-up | manual+e2e |
| TC-035 | R-DATA-006,R-GEO-004 | legitimate point-only location anomaly | fixture with valid geocoded non-city location lacking any matched boundary | inspect map marker, panel data, and linked documents | point-only display is treated as valid when docs/identity are otherwise coherent; missing polygon alone is not logged as data corruption | manual+e2e |
| TC-036 | R-DATA-007,R-API-003 | hierarchy materialization anomaly | fixture where location names imply a country/region relationship but hierarchy rows are intentionally absent or incomplete | GET `/api/map/location/{id}/documents` and inspect panel scope | document aggregation follows `bi_location_hierarchy` only; missing descendants are classified as analytics hierarchy issue rather than frontend matching bug | automated+manual |
| TC-037 | R-DATA-008 | rolled-up analytics projection anomaly | fixture with multiple mentions, differing evidence, or mixed precisions under the same rolled-up BI linkage | inspect document/location payloads and panel output | QA treats mention counts and evidence quote as rolled-up analytics projections and does not expect per-mention confidence/precision in presentation responses | automated+manual |
| TC-038 | R-DATA-009,R-PANEL-002,R-API-010 | PDF absence with valid linkage anomaly | fixture where document/location links exist but `latest_snapshot_id`/`pdf_blob` is absent | inspect card UI and request PDF endpoint | document can be correctly linked on map while showing `No PDF preview` and returning PDF `404`; QA does not classify missing PDF alone as map-link defect | automated+manual |
| TC-039 | R-DATA-010,R-API-001 | coordinate filtering anomaly | fixture with valid-looking location rows upstream but null/NaN/out-of-range coordinates | GET `/api/map/locations` and inspect rendered map | invalid-coordinate rows are excluded from presentation payload/map rendering, and QA classifies absence as input filtering rather than frontend disappearance bug | automated |

## Automation Plan
- Current automated baseline:
  - `tests/test_presentation_api.py`
  - `tests/test_presentation_repository.py`
- Highest-value automation additions for current UI:
  - Playwright smoke coverage for startup readiness vs. background boundary hydration
  - Playwright interaction coverage for search-active panel isolation, mode-pill transitions, declutter controls, and modal close semantics
  - Browser-level regression for overlapping location selection preferring docs-backed peers on hover and click
  - Browser-level geometry regression for neutral blue non-city fallback points
  - API-level regression for unresolved location-document payloads, PDF `416`, and boundaries cache/detail variants
  - Diagnostic fixtures for stale persisted geocodes, duplicate semantic peers, hierarchy omissions, and missing-PDF-but-valid-link cases

## Pipeline-Oriented QA Notes
- When presentation behavior looks wrong, classify the failing layer before filing a UI defect:
  - geocoder identity/top-result problem
  - analytics hierarchy/materialization problem
  - geometry coverage/matching problem
  - presentation matching/rendering problem
- Record whether the observed issue would require:
  - frontend-only deploy
  - analytics rebuild
  - re-geocode + analytics rebuild
  - source-data/canonical refresh
- Use live API inspection to separate these cases whenever possible:
  - `/api/map/locations`
  - `/api/map/boundaries`
  - `/api/map/location/{id}/documents`
  - `/api/map/document/{id}/locations`
  - `/api/search`
