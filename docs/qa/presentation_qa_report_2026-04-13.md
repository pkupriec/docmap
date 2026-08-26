# Presentation QA Report

Date: 2026-04-13
Workspace: `D:\Sources\docmap`
Runtime exercised: `http://localhost:8080`

## 1. Executive Summary

Overall UI quality impression:
The presentation UI is already usable and the core search, panel, document, PDF, and pagination flows are working. The biggest issues are state/label polish problems in the presentation layer, plus one API-contract problem in the low-detail boundaries path and some clearly duplicated/stale upstream location data that makes search and selection feel less trustworthy than the UI itself.

Total counts:
- confirmed bugs: 3
- likely upstream data issues: 2
- ambiguous items: 3
- UX improvements: 5

## 2. Confirmed Bugs

### BUG-001
- Title: Search result rank pills show admin-level regions as `Unknown`
- Severity: medium
- Reproduction steps:
1. Open the presentation UI.
2. Search for `United States`.
3. Inspect the location chips in the search results.
- Observed behavior:
  The chips for `California, United States` and `Florida, United States` are rendered as `Unknown`.
- Expected behavior:
  Admin-level regions should render as an admin-region label, not `Unknown`.
- Likely layer:
  presentation matching/rendering issue
- Evidence:
  `/api/search?q=United States` returns rows like `California, United States` with `location_rank=admin_level_4`.
  The frontend formatter in `services/presentation/frontend/src/App.tsx` only maps `admin_region`/`region`, so raw `admin_level_*` values fall through to `Unknown`.
  Live snapshot showed buttons `Unknown California, United States` and `Unknown Florida, United States`.
- Required remediation type:
  frontend-only change

### BUG-002
- Title: PDF modal prevents the documented "click a different card while modal is open" behavior
- Severity: medium
- Reproduction steps:
1. Open a location-driven document list.
2. Click a PDF thumbnail to open the modal.
3. Attempt to click another document card behind the modal.
- Observed behavior:
  The full-screen backdrop and iframe intercept pointer events, so the second card cannot be clicked.
- Expected behavior:
  Clicking a different document card while a PDF modal is open should close the current modal as documented in the UX spec and checklist.
- Likely layer:
  presentation matching/rendering issue
- Evidence:
  Playwright click attempt on another card failed with: `iframe ... subtree intercepts pointer events`.
  The modal/backdrop structure in `services/presentation/frontend/src/App.tsx` covers the whole UI.
- Required remediation type:
  frontend-only change

### BUG-003
- Title: `/api/map/boundaries?geometry_detail=low` changes the feature set instead of only reducing geometry detail
- Severity: high
- Reproduction steps:
1. Request `GET /api/map/boundaries?rank_filter=default&geometry_detail=full`.
2. Request `GET /api/map/boundaries?rank_filter=default&geometry_detail=low`.
3. Compare feature counts and `location_id` sets.
- Observed behavior:
  The low-detail variant is not just simplified geometry. It returns a materially different feature set.
- Expected behavior:
  Low-detail mode should preserve the same logical boundary coverage and only reduce geometry complexity.
- Likely layer:
  presentation matching/rendering issue
- Evidence:
  `default/full`: 1433 features.
  `default/low`: 1156 features.
  Comparison showed 288 `(location_id, rank)` pairs missing from low detail and 11 extras present only in low detail.
  `services/presentation/backend/repository.py` serves `default+low` from a separate artifact file, which appears stale or inconsistent with the DB-backed full response.
- Required remediation type:
  source/canonical refresh
  More specifically: regenerate the low-detail artifact or stop serving a divergent artifact for this endpoint.

## 3. Upstream Data / Pipeline Issues

### DATA-001
- Title: Duplicate semantic London rows create confusing search duplicates and likely overlapping map candidates
- Why this is not primarily a frontend bug:
  The API already returns multiple distinct location rows for the same semantic place and coordinates, so the frontend is only exposing the duplicates it is given.
- Evidence from UI/API:
  `/api/search?q=london` returned:
  `London, United Kingdom` with 130 docs,
  `London, England, United Kingdom` with 1 doc,
  `London, England` with 0 docs,
  all at `51.5074456, -0.1277653`.
  The live search panel showed these as separate chips.
- Likely required rebuild/reprocess action:
  re-geocode + analytics rebuild
  A canonical/alias refresh may also be needed if the duplicate rows come from stale canonical identity data.

### DATA-002
- Title: Semantically duplicate city rows can still resolve to zero documents
- Why this is not primarily a frontend bug:
  The issue is already visible in the API payloads. A duplicate city row with the same real-world identity is persisted separately and does not inherit the documents from its semantic peer.
- Evidence from UI/API:
  `GET /api/map/location/f2395d72-6f84-40f9-8f69-47d2b44fb73a/documents` for `London, England` returned `total_items=0`, even though another London row at the same coordinates has 130 docs.
  This points to duplicate semantic location rows and/or missing consolidation upstream.
- Likely required rebuild/reprocess action:
  re-geocode + analytics rebuild

## 4. Ambiguous Items

### AMBIG-001
- What looks wrong:
  Many visible cards initially show `No PDF preview` even though the card metadata says `PDF: Available`, and the PDF endpoint returns `200`.
- Competing explanations:
  The thumbnail is still rendering lazily and the placeholder text is just misleading.
  Or `pdfjs-dist` is failing on some files and the placeholder is masking a real render failure.
- What to check next:
  Add a distinct loading state for thumbnails, watch thumbnail network/render timing, and log pdf.js thumbnail failures explicitly.

### AMBIG-002
- What looks wrong:
  City polygon threshold behavior and specialty-rank polygon behavior could not be validated from the live dataset.
- Competing explanations:
  The implementation may be correct, but the current boundary data simply lacks `city`, `national_park`, and `desert` features.
  Or those geometries are missing because the boundary pipeline is incomplete.
- What to check next:
  Use a fixture or dataset that definitely includes city/specialty boundaries, then retest zoom-threshold and polygon-click semantics directly.

### AMBIG-003
- What looks wrong:
  The initial loading copy likely does not match the current spec text.
- Competing explanations:
  The app code currently renders `Loading locations...`, which differs from the spec/checklist text.
  But the live transition was too fast to capture under normal localhost timing.
- What to check next:
  Re-run with throttled or delayed `/api/map/locations` and `/api/map/boundaries` responses to capture the exact startup messaging path in-browser.

## 5. UX Improvement Opportunities

### UX-001
- Title: Search mode keeps showing an unrelated location selection pill
- Current experience:
  After pinning or hovering a location, changing the search query can leave the selection pill showing a stale place that is unrelated to the current search context.
- Why it is confusing / not nice / not user-friendly:
  The right panel says `Search: 173` or `Search: United States` while the summary pill still says `London, United Kingdom` or another hovered map location, which feels like mixed scopes.
- Suggested improvement:
  Either clear stale selection summary when the query changes materially, or label the pill explicitly as map hover/pin state separate from search scope.
- Priority: high

### UX-002
- Title: `No PDF preview` is used as both "missing PDF" and "thumbnail not ready yet"
- Current experience:
  Cards can say `PDF: Available` while the thumbnail button says `No PDF preview`, then later render normally.
- Why it is confusing / not nice / not user-friendly:
  Users cannot tell whether the PDF is actually missing or the preview is still loading.
- Suggested improvement:
  Split the states into `Loading preview`, `Preview unavailable`, and `No PDF`.
- Priority: high

### UX-003
- Title: Duplicate semantic location search results are hard to disambiguate
- Current experience:
  Search results can show multiple near-identical London variants with no doc-count cue in the chip itself.
- Why it is confusing / not nice / not user-friendly:
  The user has to guess which result is the "real" operational one, and some duplicates have zero docs even though a semantic peer has many.
- Suggested improvement:
  Add doc counts to chips, group obvious semantic duplicates, or visually down-rank zero-doc duplicates when a stronger same-coordinate peer exists.
- Priority: high

### UX-004
- Title: Collapsed quick actions are too cryptic
- Current experience:
  In collapsed mode the left strip exposes bare `S` and `C` buttons.
- Why it is confusing / not nice / not user-friendly:
  The actions are not discoverable without hover/tooltips, which makes the collapsed state feel less polished.
- Suggested improvement:
  Use icons plus tooltips, or short labels such as `Search` and `Clear`.
- Priority: medium

### UX-005
- Title: Missing favicon creates a small but visible polish gap
- Current experience:
  The browser logs a `404` for `/favicon.ico` on startup.
- Why it is confusing / not nice / not user-friendly:
  It is minor, but it contributes to an unfinished feel and adds avoidable console noise.
- Suggested improvement:
  Add a favicon or stop referencing one implicitly.
- Priority: low

## 6. Coverage Notes

Which test cases were exercised:
- TC-001 shell/layout
- TC-002 collapse/quick actions
- TC-007 mode pill and selection summary behavior
- TC-008 idle and contextual empty transitions partially
- TC-017 search activation threshold behavior
- TC-018 search-active panel isolation partially
- TC-019 search/map sync partially
- TC-020 document card rendering and outbound SCP links visually
- TC-021 document visualization, pin, and offscreen count
- TC-022 declutter controls visibility
- TC-023 PDF modal open/close semantics partially
- TC-024 `Esc` reset behavior
- TC-028 pagination / `Load more`
- TC-010 boundaries detail/filter behavior via API
- TC-012 unresolved location-documents API
- TC-013 missing document API
- TC-014 PDF `404`, `206`, `416`
- TC-016 search API behavior
- TC-032 / TC-034 style data-anomaly investigation through live search/API evidence

Which were not fully exercised:
- TC-004, TC-005, TC-006 startup/loading/degraded-startup UI states
- TC-025, TC-026, TC-027 full geometry rendering and overlap behavior
- TC-029 density overlay API was not directly inspected
- TC-030, TC-031 architecture/runtime separation were not re-audited beyond health and read-only endpoint usage
- TC-033, TC-035, TC-036, TC-037, TC-038, TC-039 were only partially covered or inferred from current live data

Why not:
- Local startup was too fast to reliably capture loading/degradation copy without request throttling/mocking.
- The live boundary dataset does not currently expose the full set of geometry ranks needed for city-threshold and specialty-rank validation.
- Overlap selection is difficult to certify from the current live browser session without a purpose-built fixture and more precise map-target instrumentation.

## 7. Recommended Next Fix Order

1. Fix `BUG-003` first so the low-detail boundaries endpoint stops violating its own contract and introducing hidden map inconsistency.
2. Fix `BUG-001` next because the `Unknown` rank labels are user-visible, frequent, and cheap to correct.
3. Fix `BUG-002` so the PDF modal behavior matches the documented interaction model.
4. Address `DATA-001` and `DATA-002` together as a pipeline cleanup pass for duplicate semantic locations.
5. Improve `UX-002` and `UX-001` next because they directly affect trust and clarity in the right panel.
6. Do a second targeted QA pass with throttled startup and geometry fixtures to close the remaining ambiguous coverage gaps.
