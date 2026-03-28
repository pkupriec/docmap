# Presentation Test Cases Matrix

| test_id | requirement_reference | feature_area | preconditions | steps | expected_result | automation_status |
|---|---|---|---|---|---|---|
| TC-001 | R-SHELL-001,R-SHELL-004 | shell/layout | presentation service running | Open `/` | 3-region desktop layout with left/map/right areas and search field | manual+e2e |
| TC-002 | R-SHELL-002 | shell/layout | app loaded | Click collapse toggle twice | Left panel collapses to thin strip and expands back, toggle remains visible | manual+e2e |
| TC-003 | R-SHELL-005,R-MAP-004 | shell/reset | app loaded with selected location + pinned doc + open modal | Click `Clear` | pinned location/document cleared and modal closed | manual+e2e |
| TC-004 | R-STATE-001,R-STATE-002 | startup/state | backend reachable | Hard refresh page | `Loading...` shown initially, then ready state after both startup calls succeed | manual+e2e |
| TC-005 | R-STATE-003 | startup/error | force startup API failure | Load page | `Unable to load data.` shown | manual |
| TC-006 | R-API-001 | API locations | test DB fixture | GET `/api/map/locations` | deterministic rows, valid coordinates, required fields present | automated |
| TC-007 | R-API-002 | API boundaries | test DB fixture with boundary row | GET `/api/map/boundaries?lite=1` | GeoJSON FeatureCollection with polygon/multipolygon features | automated |
| TC-008 | R-API-003,R-PANEL-003 | API fallback docs | hierarchy fixture (city->country docs) | GET `/api/map/location/{city}/documents` | nearest depth resolution and fallback metadata returned; deduped cards | automated |
| TC-009 | R-API-004 | API document card | fixture with doc | GET `/api/map/document/{id}` | required card payload fields present | automated |
| TC-010 | R-API-005 | API PDF | fixture with pdf_blob | GET `/api/map/document/{id}/pdf` and `Range` request | full response and partial range response work; 404 for missing | automated |
| TC-011 | R-API-006 | API doc locations | fixture with mention counts | GET `/api/map/document/{id}/locations` | deterministic ordering + payload fields | automated |
| TC-012 | R-API-008,R-API-009 | API search | fixture with matching docs/locations | GET `/api/search?q=<query>&limit=5` | deterministic deduped results, caps at 5, SCP+numeric+location matches | automated |
| TC-013 | R-LIVE-001 | search activation | app loaded | Type <3 chars then 3+ chars in search | no active search below threshold; active search at >=3 chars | manual+e2e |
| TC-014 | R-PANEL-002,R-MAP-002 | search/panel isolation | search active | hover location on map | right panel remains search-driven, map interaction still works | manual+e2e |
| TC-015 | R-LIVE-002,R-LIVE-003 | search/map sync | app loaded with known search hits | run single-result and multi-result search flows | one result centers map; multiple results fit bounds; doc-only searches fetch linked coords | manual+e2e |
| TC-016 | R-PANEL-004,R-PANEL-005 | document card | location/search results available | inspect cards and click SCP link | SCP number/location/thumbnail shown; link opens in new tab | manual+e2e |
| TC-017 | R-PANEL-006,R-PANEL-007,R-LIVE-005 | document visualization | cards available | hover then click card, drag map | umbrella links render on hover/pin; pinned survives drag | manual+e2e |
| TC-018 | R-LIVE-004 | viewport recompute | pinned document with multiple links | move map viewport | visible links/offscreen count recompute with viewport changes | manual+e2e |
| TC-019 | R-PANEL-008,R-PANEL-009 | PDF modal behavior | card with pdf_url | click thumbnail, close by button/backdrop | modal opens centered; close button/backdrop close modal only | manual+e2e |
| TC-020 | R-MAP-005 | keyboard reset | pinned location/doc and optional modal | press `Esc` | pinned state cleared; modal also closes if open | manual+e2e |
| TC-021 | R-GEO-001,R-GEO-003 | geometry matching | boundaries + locations with rank/id cases | interact with map at multiple zooms | city threshold behavior and non-city polygon behavior follow rank and matching rules | manual+e2e |
| TC-022 | R-GEO-004 | geometry fallback color | location lacking boundary | inspect fallback marker | missing-boundary non-city point rendered red | manual+e2e |
| TC-023 | R-GEO-005,R-EXCL-001 | architecture guard | runtime running | inspect network/backend behavior during render | no runtime geometry generation writes; presentation read-only | automated+manual |
| TC-024 | R-CTRL-001,R-CTRL-003 | service separation | docker compose stack | start presentation + check `/healthz` | presentation independent service, health returns ok | manual+automated |

## Automation Plan
- Existing automation baseline: `tests/test_presentation_api.py`.
- Add/expand automated tests for:
  - search query normalization behavior in response (`query` trimmed expectation)
  - fallback resolution scoping and deterministic selection
  - boundary `lite` payload shape filtering
  - PDF range/error handling edge cases
- UI behavioral checks executed through Playwright script for smoke + interaction paths.
