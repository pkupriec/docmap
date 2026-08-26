# Next Session Prompt: Baked Interactive Geometry Optimization

Copy-paste the prompt below into the next Codex session.

---

Read project context starting from `docs/agent/INDEX.md`.

Then continue the baked interactive geometry optimization work using:
- `docs/roadmap/TASKS/baked-interactive-geometry-optimization-plan.md`
- `docs/roadmap/TASKS/baked-interactive-geometry-optimization-development-prompt.md`

Task for this session:
- Execute **Phase A only** from `baked-interactive-geometry-optimization-plan.md`.
- Do not skip ahead to later phases.

Phase A goals:
- establish the measured UI baseline for current presentation behavior
- compare at least:
  - `pmtiles`
  - standard vector tiles directory
- document the canonical baked artifact format decision using measurement
- define the cutover contract where:
  - normal viewing uses baked geometry
  - live API remains only for selected/highlighted geometry
  - no backward-compatible normal-view fallback is required

Important constraints:
- keep analytics ownership explicit
- keep presentation runtime read-only
- keep the pipeline order invariant intact
- optimize for end-user smoothness and low machine load
- do not broaden scope into unrelated cleanup
- keep docs and implementation aligned in the same change set when behavior or assumptions change

Expected output:
1. Summary of Phase A work
2. Measurements collected
3. Artifact format comparison and decision
4. Canonical contract decisions recorded
5. Files changed
6. Residual risks
7. Recommended next phase

If Phase A reveals that the currently drafted thresholds, preload policy, or artifact contract should be sharpened before Phase B, update the plan docs in the same change set before stopping.

---
