# Presentation Runtime Performance Remediation Plan

Date: 2026-04-14
Owner: Presentation runtime team
Status: Proposed next implementation task

## 1. Objective

Eliminate avoidable client and presentation-backend load by fixing the highest-impact runtime bottlenecks in a strict sequence, while moving stable expensive work out of request time and into build/analytics/startup preparation where appropriate.

Target outcomes:
- first meaningful render (map shell + immediately usable points): <= 1.0s after app load on local stack
- initial interactive map state without browser hitching on local stack
- pan/zoom interaction remains responsive while boundaries stream in progressively
- location selection and document hover do not trigger noticeable UI stalls
- presentation API request cost is proportional to visible scope and selected content
- repeated reads avoid rebuilding or recomputing data that can be prepared ahead of time

## 2. Validated Current State (Code-Backed)

Validated from implementation on 2026-04-14:
- presentation frontend bootstraps by loading all locations up front from `GET /api/map/locations`
- `bi_locations` is read in full with no viewport or pagination gate
- map rendering derives polygons/points by scanning all loaded locations on the client
- boundary delivery is chunk-aware but still performs one request per missing chunk and merges chunk responses through repeated React state updates
- boundary repository parses `feature_json` row-by-row at request time
- `get_location_documents` performs several repository calls and repeats scope counting work
- every repository call opens a new database connection via `services/common/db.py`
- search uses `LOWER(...) LIKE '%term%'` patterns over BI text fields without task-visible supporting indexes in canonical schema
- PDF thumbnails are rendered client-side through `pdfjs-dist`, while PDF bytes are read from `document_snapshots.pdf_blob`
- canonical `database/schema.sql` still lags runtime migration-backed `bi_admin_boundaries` envelope/index support

Primary heavy paths:
- `services/presentation/frontend/src/App.tsx`
- `services/presentation/frontend/src/MapView.tsx`
- `services/presentation/frontend/src/PdfThumbnail.tsx`
- `services/presentation/backend/api.py`
- `services/presentation/backend/repository.py`
- `services/common/db.py`
- `services/common/migrations.py`
- `database/schema.sql`

## 3. Scope

In scope:
- presentation frontend runtime flow and rendering cost
- presentation backend API and repository query efficiency
- BI/search/index support needed for presentation read paths
- moving stable expensive work out of request-time/runtime hot paths
- canonical docs/schema alignment where performance-critical runtime assumptions currently live only in migrations
- measurement and verification updates

Out of scope:
- control plane behavior redesign
- geocoder semantics redesign
- analytics correctness changes unrelated to presentation-read performance
- auth/deployment hardening beyond performance-relevant runtime behavior

## 4. Design Principles

1. Fix one class of bottleneck at a time.
   - Do not mix broad renderer rewrites with query/index work in the same phase.
   - Each phase must produce measurable improvement or a clear enabling change.

2. Move stable work earlier.
   - If data can be precomputed during analytics, build, or startup migration, do not keep recomputing it in hot requests or interaction paths.

3. Keep presentation read-only.
   - Baking ahead is acceptable only in owner-approved write domains:
     - analytics-owned BI projections/materializations
     - startup-compatible migrations
     - build-generated frontend assets
   - presentation runtime itself remains read-only.

4. Preserve deterministic behavior.
   - identical DB state and request shape must yield deterministic output ordering and content.

5. Prefer bounded payloads and bounded work.
   - startup payloads, per-interaction requests, and per-frame render work must all scale with visible need, not total dataset size.

## 5. Work That Should Be Baked Ahead Instead of Done at Runtime

These items should be treated as preferred precomputation candidates unless an implementation pass proves they are unnecessary.

### A. BI / analytics precomputation

Best candidates:
- boundary envelope metadata for `bi_admin_boundaries`
- optional chunk/grid membership metadata for polygons if envelope filtering is still too expensive
- search-support normalized fields or helper projections if current BI tables remain too scan-heavy
- document preview artifacts or first-page thumbnails derived from PDFs
- document top-location display strings if they are repeatedly recomputed from joins/window functions
- explicit semantic city peer/group identifiers if city dedupe/grouping remains expensive at read time

Rationale:
- these values are derived, deterministic, and owned by analytics/BI preparation rather than by presentation requests
- precomputing them reduces Python request-time parsing, repeated DB joins, and browser-side CPU work

### B. Startup migration / schema preparation

Best candidates:
- schema patches that are already runtime assumptions in repository code
- missing indexes for known hot queries
- backfills for derived envelope/search helper columns

Rationale:
- if request-time code depends on a column or index, that support should not exist only as an implicit runtime patch

### C. Frontend build-time or asset-time preparation

Best candidates:
- code splitting/lazy-load boundaries for map/PDF-heavy modules
- prebuilt thumbnail or preview asset delivery path
- static map style and non-dynamic config extraction

Rationale:
- large stable client code/assets should not block the first useful interaction path

## 6. Sequential Remediation Phases

### Phase A - Measurement, Canonical Schema Alignment, and Request Cost Visibility

Purpose: establish accurate perf visibility and eliminate schema/runtime drift that hides bottlenecks.

Tasks:
1. Add/request consistent timing and payload logging around:
   - `/api/map/locations`
   - `/api/map/boundaries`
   - `/api/map/location/{id}/documents`
   - `/api/map/document/{id}/locations`
   - `/api/search`
2. Add local verification guidance for:
   - startup timings
   - boundary request counts by viewport move
   - location/documents query timings
   - search timings
3. Promote boundary-envelope schema support from migrations into canonical schema/docs:
   - `min_lon`
   - `min_lat`
   - `max_lon`
   - `max_lat`
   - supporting indexes
4. Audit and document all current presentation hot-path indexes and missing indexes.

Acceptance:
- canonical schema and runtime assumptions match for `bi_admin_boundaries`
- perf logging exists for all major presentation read paths
- no hidden migration-only performance dependency remains undocumented

### Phase B - Database Connection and API Roundtrip Reduction

Purpose: remove avoidable per-request backend overhead before deeper query work.

Tasks:
1. Replace one-connection-per-call behavior in `services/common/db.py` with pooled/reused connections appropriate for FastAPI read traffic.
2. Collapse multi-call `get_location_documents` flow where possible:
   - avoid repeated count queries over the same scope
   - avoid separate lookup for location display when it can be returned in the scoped query
3. Review other presentation endpoints for repeated repository roundtrips and fuse them where safe.
4. Keep all results deterministic and contract-compatible.

Acceptance:
- presentation requests no longer create a fresh DB connection for every repository call
- location documents path performs materially fewer DB roundtrips
- measured latency improvement is visible before any renderer changes

### Phase C - Search and BI Index Hardening

Purpose: make text search and document-location lookups scale with the actual query patterns.

Tasks:
1. Profile and harden `search()` queries:
   - `bi_documents.canonical_number`
   - `bi_locations.normalized_location`
   - `bi_locations.city`
   - `bi_locations.region`
   - `bi_locations.country`
2. Add supporting functional or trigram indexes through canonical schema + startup-compatible migration path.
3. Review document/location lookup indexes used by:
   - `list_document_locations`
   - `list_location_documents`
   - alias-resolution lookups
4. If search still requires too much runtime normalization, add analytics-owned precomputed helper fields/materializations.

Acceptance:
- search no longer relies on raw full-scan `LIKE '%term%'` paths for ordinary usage
- BI schema exposes the indexes required by presentation hot queries
- search latency remains bounded as BI row counts grow

### Phase D - Startup Payload Reduction and Progressive Location Delivery

Purpose: stop forcing the browser to ingest and process the entire location universe before it becomes useful.

Tasks:
1. Rework `/api/map/locations` delivery model so startup is not an unconditional full-table load.
2. Choose one acceptable implementation:
   - viewport/zoom-scoped location reads
   - coarse bootstrap tiers followed by progressive hydration
   - server-provided summary/cluster path at low zoom
3. Reduce broad client-side recomputation over all locations in:
   - initial boot
   - viewport changes
   - search highlight changes
4. Preserve deterministic point rendering semantics and fallback behavior.

Acceptance:
- startup no longer requires a full `bi_locations` read for first useful map render
- client CPU cost at boot is materially lower
- initial interaction remains responsive before all optional data is hydrated

### Phase E - Boundary Delivery Consolidation and Runtime Parsing Reduction

Purpose: make boundary delivery cheaper both on the wire and in backend request handling.

Tasks:
1. Replace one-request-per-chunk fetch bursts with batched chunk delivery where practical.
2. Reduce repeated React state churn during chunk merge.
3. Eliminate unnecessary request-time JSON parsing/serialization work for `bi_admin_boundaries`.
4. If needed, move beyond envelope metadata to analytics-baked chunk/grid membership so request-time filtering is a metadata lookup rather than repeated row parsing.
5. Keep explicit selected/highlighted polygon inclusion behavior intact.

Acceptance:
- viewport-driven boundary loads use fewer requests and fewer client merge passes
- backend boundary request cost is driven by precomputed metadata more than Python row parsing
- boundary-ready time improves without correctness regression

### Phase F - Map Interaction CPU Hot Path Cleanup

Purpose: remove avoidable per-interaction client work that causes visible stalls.

Tasks:
1. Reduce broad `locations` scans in `MapView`.
2. Remove or constrain O(N polygon) click fallback behavior.
3. Stabilize/reduce deck.gl layer recreation and hot `useMemo` recomputation.
4. Move highlight/pulse behavior away from React-state-driven 50 ms rerenders if still measurable.
5. Review DOM-to-map link overlay work and keep it proportional to visible/active content only.

Acceptance:
- click/hover/selection interactions no longer spike CPU on representative data
- map interaction p95 remains within target under ordinary use
- search highlight mode and document-link visualization remain responsive

### Phase G - PDF and Document Card Cost Removal

Purpose: stop spending large amounts of client and backend work on per-card PDF decoding.

Tasks:
1. Replace browser-side `pdfjs-dist` thumbnail generation with a baked-ahead preview path when feasible.
2. Preferred implementation:
   - analytics/offline/server-generated first-page thumbnail assets
   - lightweight image delivery to cards
3. Secondary improvements if full baking is deferred:
   - narrower lazy-load margins
   - stricter concurrency bounds
   - deferred loading only for actually visible cards
4. Review PDF endpoint delivery path for memory amplification caused by whole-blob reads before range slicing.

Acceptance:
- card rendering no longer triggers client-side PDF decoding in the normal path
- PDF-related bundle/runtime cost drops materially
- document panel remains responsive with many cards

### Phase H - Bake-Ahead Materialization Pass

Purpose: formalize all proven precomputations so the optimized runtime stays lean.

Tasks:
1. Convert validated runtime-heavy derived values into analytics-owned or build-owned artifacts.
2. Candidate deliverables:
   - thumbnail/previews
   - location grouping helpers
   - chunk/grid membership metadata
   - search-helper projections/materialized views
   - pre-ranked or prejoined document display helpers where justified by profiling
3. Update docs to distinguish:
   - canonical data
   - BI/materialized helpers
   - runtime caches

Acceptance:
- repeated expensive presentation computations have an explicit precomputed home
- runtime code paths clearly prefer baked artifacts over recalculation
- ownership boundaries remain documented and explicit

## 7. Recommended Execution Order

1. Phase A - Measurement, Canonical Schema Alignment, and Request Cost Visibility
2. Phase B - Database Connection and API Roundtrip Reduction
3. Phase C - Search and BI Index Hardening
4. Phase D - Startup Payload Reduction and Progressive Location Delivery
5. Phase E - Boundary Delivery Consolidation and Runtime Parsing Reduction
6. Phase F - Map Interaction CPU Hot Path Cleanup
7. Phase G - PDF and Document Card Cost Removal
8. Phase H - Bake-Ahead Materialization Pass

Execution rule:
- do not start renderer-heavy optimization work before backend connection/query/index fixes are measured
- do not introduce new baked artifacts until the runtime hotspot has been measured and proven worth materializing

## 8. Deliverables

Required code deliverables across the full plan:
- presentation perf instrumentation and verification hooks
- canonical schema/index updates for hot presentation reads
- connection pooling / reduced roundtrip API paths
- indexed and/or materialized search support
- progressive location delivery strategy
- batched boundary delivery and lower-runtime parse cost
- lighter map interaction hot paths
- baked-ahead preview/materialization path for stable heavy derived artifacts

Required docs updates:
- `docs/presentation/PRESENTATION_ARCHITECTURE.md`
- `docs/presentation/PRESENTATION_DATA_CONTRACT.md`
- `docs/presentation/PRESENTATION_API_SPEC.md`
- `docs/operations/VERIFICATION.md`
- task-specific QA/perf notes as needed

## 9. Verification Protocol

For each phase, record before/after:
- first meaningful render
- time to first useful interaction
- boundary-ready time
- request counts during a representative pan/zoom sequence
- latency and payload size for each major presentation endpoint
- browser main-thread activity for:
  - startup
  - location selection
  - search
  - document hover/pin
- DB query timings and plan quality for changed endpoints

Required verification scenarios:
1. Cold startup on local stack
2. Low-zoom world view pan
3. Regional zoom pan
4. Select location with many documents
5. Search for SCP number and location text
6. Hover/pin document with multiple linked locations
7. Scroll document cards with previews enabled

## 10. Risks and Mitigations

Risk: schema/index changes drift again from canonical docs.
Mitigation: any migration-backed perf-critical support must be promoted to canonical schema/docs in the same phase.

Risk: moving work into BI/materialization layers blurs ownership.
Mitigation: keep derived artifacts explicitly owned by analytics/build layers and document them as such.

Risk: reducing startup payload changes visual expectations.
Mitigation: preserve deterministic fallback rendering and verify visible behavior explicitly.

Risk: batching boundary requests increases individual payload size too far.
Mitigation: tune chunk batching with concrete measurements and keep explicit focus requests separate if needed.

Risk: thumbnail baking adds storage/build complexity.
Mitigation: only promote it after confirming that PDF decode remains a material cost after lower-effort mitigations.

## 11. Immediate Next Step

Start with Phase A and produce a measured baseline plus canonical schema/index alignment report before making behavioral optimizations.
