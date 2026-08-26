# Baked Interactive Geometry Optimization - Phase A Report

Date: 2026-04-17  
Scope: Phase A only (`baseline + candidate benchmark + contract decision`)

## 1. Measurement Setup

Environment:
- local compose stack (`presentation` at `http://localhost:8080`)
- browser automation via Playwright (Chromium)
- source geometry: `services/analytics/assets/admin_boundaries.geojson`

Commands used:
- `python services/presentation/scripts/measure_phase_a_ui_baseline.py`
- `python services/analytics/scripts/compare_phase_a_artifact_formats.py`

Generated measurement artifacts:
- `docs/qa/baked_interactive_geometry_phase_a_ui_baseline_2026-04-17.json`
- `docs/qa/baked_interactive_geometry_phase_a_artifact_compare_2026-04-17.json`

## 2. Current UI Baseline (Live `/api/map/boundaries` Path)

### Startup baseline

- `presentation.performance.first_meaningful_render_ms`: `86.4`
- `presentation.performance.boundaries_ready_ms`: `37799.7`
- initial request count: `54`
- initial response content-length bytes (reported): `44,535,920`

### Representative scenario metrics

- `low_zoom_pan`
  - elapsed: `716.24 ms`
  - requests: `5`
  - task-duration delta: `519.82 ms`
  - heap used after: `337.533 MB`
- `regional_pan`
  - elapsed: `104,326.48 ms`
  - requests: `40`
  - response bytes (reported): `50,842,842`
  - task-duration delta: `109,454.39 ms`
  - heap used after: `617.533 MB`
- `hover_click_select`
  - elapsed: `6,418.82 ms`
  - requests: `2`
  - response bytes (reported): `52,177`
  - task-duration delta: `6,416.72 ms`
  - heap used after: `641.128 MB`
- `search_highlight`
  - elapsed: `13,796.50 ms`
  - requests: `6`
  - response bytes (reported): `7,459,857`
  - task-duration delta: `13,706.79 ms`
  - heap used after: `475.420 MB`

Summary finding:
- the current normal-view boundary flow is interaction-expensive in regional movement and creates high main-thread/heap pressure.

## 3. Candidate Artifact Comparison (`pmtiles` vs `z/x/y`)

Prototype benchmark model:
- generated identical vector-tile payloads for both candidates over representative windows:
  - low-zoom world
  - regional Europe + regional pan window
  - local focus window
- total benchmark tile set: `44` tiles
- measured repeated read + decode runs (`n=5`) for each format

Measured results:

- artifact size
  - vector tile directory: `20,968,353 bytes`
  - pmtiles: `20,968,895 bytes`
  - size ratio (`pmtiles/vector_dir`): `1.0`
- read + decode latency (median)
  - vector tile directory: `5,299.67 ms`
  - pmtiles: `5,235.18 ms`
- read calls per run
  - vector tile directory: `44`
  - pmtiles (python reader path): `132`

Decision from Phase A measurement:
- canonical baked artifact format for this project path is **standard vector tile directory (`z/x/y`)**.

Rationale:
- equivalent artifact size and no material latency gap in this harness
- pmtiles latency advantage is marginal while introducing a new protocol/runtime dependency path
- `z/x/y` keeps analytics output + static delivery simpler for deterministic rollout
- clean compatibility with required hover/click interactivity in MapLibre

## 4. Canonical Cutover Contract (Recorded in Phase A)

- normal viewing must use baked geometry only
- live API remains only for selected/highlighted geometry fetches
- no backward-compatible normal-view fallback to live viewport boundary assembly is required
- baked geometry remains interactive for hover + click select
- analytics owns artifact generation; presentation runtime remains read-only

## 5. Phase-A Sharpened Guardrails Before Phase B

- preload policy must remain viewport-first; background preload cannot outrank active interaction work
- preload concurrency must be bounded and cancellable (start with low parallelism and escalate only if measurements stay stable)
- zoom-band simplification remains the only simplification control axis (no rank-tuned simplification in this line of work)

## 6. Residual Risks

- this artifact benchmark is a local prototype harness, not yet the final browser-integrated map-render benchmark for baked mode.
- `Full precise` may still create heavy client load when fully materialized; Phase B/C must keep it available while preserving default-path smoothness.
- reported response byte totals based on `content-length` headers can under-report some responses; Phase F should include encoded/decoded byte accounting in automated perf runs.
