# Presentation UX Alignment And Performance Handoff

## Documentation Changes Summary

The presentation docs were updated to match the current implemented UX and runtime behavior instead of older intended design language.

What changed:

- `PRESENTATION_ARCHITECTURE.md`
  - replaced static-geometry wording with the current API-backed boundary flow from `bi_admin_boundaries`
  - expanded the real backend read surface to include `bi_admin_boundaries` and `document_snapshots`
  - documented current startup blocking, search-driven map focus, geometry matching, and exact close/reset behavior
- `PRESENTATION_API_SPEC.md`
  - added the live `/api/map/boundaries` contract
  - clarified current hierarchy fallback reality, search short-query behavior, document-only search map focus, and PDF source path
- `PRESENTATION_DATA_CONTRACT.md`
  - aligned table sources and payload fields with the implemented responses
  - documented the weaker implementation guarantees around fallback and boundary matching
  - captured the current boundary feature contract and current `location_display` behavior
- `PRESENTATION_UX_SPEC.md`
  - aligned search, geometry fallback, loading, modal, `Esc`, pinned-state, and document-link behavior to current code
  - removed stronger guarantees that the current implementation does not actually enforce

Why:

- the implemented UX is the source of truth for the next phase
- the next optimization pass must preserve current interaction semantics while reducing client-machine load

## Final Optimization Task For GPT-5.3-codex

Use the following prompt as-is for the next implementation phase.

### Prompt

You are optimizing the current presentation implementation in `D:\Sources\docmap`.

Treat the currently implemented behavior as the source of truth even if older docs or comments imply a different ideal design. Do not redesign UX. Optimize implementation only.

Your goal is to materially reduce client-machine load while preserving the current visible interaction model.

Priority order:

1. reduce startup payload / startup parse work
2. reduce re-render and recompute pressure during map movement
3. reduce PDF thumbnail CPU, memory, and network cost
4. optimize backend query/payload paths only where needed to support the first three goals

### Mandatory Read Set

Read these files first and do not broaden scope unless they prove insufficient:

1. `D:\Sources\docmap\TASKS\presentation_ux_alignment_and_perf_handoff.md`
2. `D:\Sources\docmap\services\presentation\frontend\src\App.tsx`
3. `D:\Sources\docmap\services\presentation\frontend\src\MapView.tsx`
4. `D:\Sources\docmap\services\presentation\frontend\src\PdfThumbnail.tsx`
5. `D:\Sources\docmap\services\presentation\frontend\src\api.ts`
6. `D:\Sources\docmap\services\presentation\frontend\src\types.ts`
7. `D:\Sources\docmap\services\presentation\backend\api.py`
8. `D:\Sources\docmap\services\presentation\backend\repository.py`
9. `D:\Sources\docmap\tests\test_presentation_api.py`

### Optional Read Set Only If Blocked

Only if the mandatory set leaves a concrete blocker, read one or more of:

- `D:\Sources\docmap\services\analytics\service.py`
- `D:\Sources\docmap\services\analytics\geometry_assets.py`
- `D:\Sources\docmap\database\schema.sql`

Do not widen scope to unrelated services or broad repo docs unless a concrete dependency forces it.

### Current Behavior You Must Preserve

- startup currently fetches locations and boundaries through the presentation API
- presentation backend serves boundaries through `/api/map/boundaries`
- frontend currently becomes ready only after both startup requests complete
- search becomes active at `3+` trimmed characters
- if search returns locations, map focus uses those locations
- if search returns only documents, frontend fetches `/api/map/document/{id}/locations` to derive focus coordinates
- city rendering:
  - polygon when a boundary exists and map zoom is `>= 3.2`
  - point below that zoom
  - point if no boundary matches
- `admin_region`, `country`, `continent`, and `ocean`:
  - polygon if boundary exists
  - point if boundary is missing
- missing-boundary non-city points are red
- city points remain blue when not selected
- boundary matching currently tries `location_id` first, then `location_rank + location_name`
- document card hover and pin drive umbrella-link visualization
- pinned document continues updating visible/offscreen linked locations as viewport changes
- PDF modal uses an iframe backed by `/api/map/document/{id}/pdf`
- PDF thumbnails are currently generated client-side with `pdfjs-dist`
- pressing `Esc` currently closes the modal if open and also clears pinned document and pinned location state
- close button / backdrop close only the modal

### Performance Context

Current known pain points:

- boundaries payload is large, about `12.8 MB` serialized in the current local dataset
- startup is blocked on locations plus boundaries together
- `MapView` pushes viewport changes upward during map movement, causing frequent root-level rerender/recompute
- document-link visibility/path computation is tied to that hot path
- `PdfThumbnail` performs client-side PDF parsing/rendering and can fan out across large document lists
- one location currently has `544` linked documents, so thumbnail work can spike badly

### Allowed Changes

You may change:

- fetch strategy
- caching strategy
- response shaping between presentation frontend/backend, if both sides are updated together and UX stays the same
- payload splitting or staged loading strategy
- memoization and state placement
- thumbnail scheduling, concurrency limiting, caching, or representation
- backend support for lighter boundary delivery if needed by the frontend optimization

### Non-Goals

Do not:

- redesign the interaction model
- change search semantics
- change selection or pinning semantics
- change `Esc` behavior
- change color meaning for current states
- remove thumbnails entirely
- remove current geometry behavior
- refactor outside the presentation service scope unless a mandatory dependency forces a minimal supporting change

### Optimization Boundaries

Optimize for lower client cost first.

Focus areas, in order:

1. Make startup cheaper without changing interaction semantics.
   - Reduce initial payload size, parse cost, or synchronous startup work.
   - If you stage expensive geometry work, do it without introducing a new UX mode or changing the meaning of existing states.

2. Reduce map-move work.
   - Keep hot viewport state close to the map if possible.
   - Avoid rerendering the whole app during drag/zoom when not necessary.
   - Avoid rebuilding large derived geometry/link structures on every map movement.

3. Make thumbnails lazy and bounded.
   - Avoid eager full-PDF parsing for large visible lists.
   - Cap concurrency.
   - Cache thumbnail results by document.
   - Prefer avoiding repeated fetch/parse of the same PDF.

4. Reduce repeated large-boundary processing.
   - Avoid reconstructing large boundary lookup structures or deck layer inputs unless the underlying data actually changed.

### Acceptance Criteria

The work is successful only if all of the following are true:

- visible UX and interaction semantics remain unchanged
- startup is noticeably lighter on client CPU/memory and feels faster
- map drag/zoom is more responsive
- high-cardinality document lists no longer create obvious thumbnail-related client spikes
- search, location selection, document hover/pin, modal behavior, and geometry fallback behavior still work exactly as before
- tests are updated or added where needed for any API changes

### Execution Notes

- prefer the narrowest implementation that addresses the hot paths
- do not start with a broad architecture rewrite
- if you introduce an API change, keep it scoped to presentation and update the frontend together
- document any intentional tradeoff in a short note at the end of your work

## Residual Risks Or Ambiguities

- Search has two thresholds today: the API accepts `q` length `>= 1`, but repository logic returns empty results below `3`, and the frontend only sends requests at `3+` characters.
- Hierarchy fallback is documented to current reality: nearest ancestor with documents. Current data makes this behave like `city -> admin_region -> country`, but the SQL does not hard-enforce that rank ladder.
- Boundary matching still has a secondary `location_rank + location_name` fallback. That is weaker than an identity guarantee and could create ambiguity if upstream data drifts.
- Modal-close behavior is intentionally asymmetric in the current implementation: close button/backdrop preserve pin state, while `Esc` clears it.
