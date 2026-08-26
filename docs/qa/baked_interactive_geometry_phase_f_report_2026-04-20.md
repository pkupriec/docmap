# Baked Interactive Geometry Optimization - Phase F Report

Date: 2026-04-20  
Scope: Phase F only (`performance validation + canonicalization protocol tightening`)

## 1. Methodology

Baseline source:
- `docs/qa/baked_interactive_geometry_phase_a_ui_baseline_2026-04-17.json`

Phase F harness:
- `services/presentation/scripts/measure_phase_f_ui_performance.py`

Harness behavior:
- replays the Phase A scenarios (`low_zoom_pan`, `regional_pan`, `hover_click_select`, `search_highlight`)
- captures:
  - first useful interaction markers (`first_meaningful_render_ms`, `boundaries_ready_ms`)
  - scenario elapsed timings
  - request counts
  - encoded payload bytes (`content-length`)
  - decoded payload bytes (`response.body()` length)
  - browser main-thread/load indicators (`TaskDuration`, `ScriptDuration`, heap, DOM nodes)
- computes threshold flags:
  - `minimum_5x_met`
  - `stretch_20x_met`

## 2. Validation Gate Outcome

Current runtime preflight failed for a valid Phase F "after" run:
- `GET /api/map/baked/manifest` returned `404`.
- Harness now hard-fails in this state to prevent invalid threshold claims.

Error:
- `RuntimeError: baked manifest unavailable at http://localhost:8080/api/map/baked/manifest (status=404); generate analytics baked artifacts before running Phase F`

## 3. Before vs After Metrics (Captured Session)

### 3.1 Baseline (Phase A, valid)

- first meaningful render: `86.4 ms`
- boundaries ready: `37,799.7 ms`
- startup requests: `54`
- startup encoded payload bytes: `44,535,920`

### 3.2 Captured "after" attempt in this session

Record:
- `docs/qa/baked_interactive_geometry_phase_f_current_invalid_legacy_runtime_2026-04-20.json`
- `docs/qa/baked_interactive_geometry_phase_f_comparison_invalid_legacy_runtime_2026-04-20.json`

Important:
- This run is **invalid for Phase F acceptance** because it was captured before preflight gates were enforced and did not prove baked-manifest availability.

Structured snapshot (invalid run):

| Scenario | Baseline elapsed ms | Captured elapsed ms | Ratio (baseline/captured) |
|---|---:|---:|---:|
| low_zoom_pan | 716.24 | 11970.15 | 0.06x |
| regional_pan | 104326.48 | 117213.58 | 0.89x |
| hover_click_select | 6418.82 | 7548.31 | 0.85x |
| search_highlight | 13796.50 | 14994.93 | 0.92x |

This table is retained only as an invalid preflight artifact and not an acceptance measurement.

## 4. Threshold Results

Because a valid baked-manifest "after" run could not be completed:
- minimum `5x` improvement: **not demonstrated**
- stretch `20x` improvement: **not met**

## 5. Limiting Factors

Primary blocker in this environment:
- analytics baked artifact manifest unavailable at runtime (`/api/map/baked/manifest` -> `404`), so canonical baked-path performance validation cannot proceed.

Operational factor observed:
- local `rebuild_admin_boundaries` attempts exceeded the session execution timeout, preventing in-session artifact regeneration.

## 6. Canonicalization / Cleanup Decisions

Implemented in this change set:
- Phase F harness now enforces validity gates:
  - baked manifest must exist
  - initial load must be baked-only for normal view
  - old normal-view `/api/map/boundaries` startup traffic invalidates the run
- Verification docs and plan updated to encode these gates explicitly.

## 7. Next Action

To complete Phase F acceptance:
1. ensure analytics-owned baked artifacts are generated and `/api/map/baked/manifest` is healthy
2. rerun `measure_phase_f_ui_performance.py`
3. replace this report's invalid-run section with a valid before/after table and final threshold decision
