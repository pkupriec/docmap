# Development Prompt: Baked Interactive Geometry Optimization

Use this prompt to execute implementation work from `docs/roadmap/TASKS/baked-interactive-geometry-optimization-plan.md`.

## Prompt

You are implementing the DocMap baked interactive geometry optimization plan.

Context:
- Read and follow `docs/roadmap/TASKS/baked-interactive-geometry-optimization-plan.md`.
- Read project context starting from `docs/agent/INDEX.md`.
- Respect project invariants from `docs/agent/PROJECT_CONSTITUTION.md`.
- The pipeline order remains `crawl -> extract -> geocode -> analytics -> export`.
- Baked geometry generation must be analytics-owned.
- Presentation runtime remains read-only.
- Normal viewing must cut over to baked geometry; live API remains only for selected/highlighted geometry.
- Backward compatibility with the old normal-view live boundary path is not required unless explicitly instructed later.

Execution model:
1. Execute one phase at a time in the documented order.
2. Measure before and after for the current phase.
3. Stop after the current phase unless explicitly instructed to continue.
4. Keep changes minimal and aligned with the active phase.
5. Record assumptions and decisions when the plan allows iteration.

Mandatory requirements:
- optimize for end-user smoothness and low machine load
- keep behavior deterministic
- keep docs, code, schema/migrations, analytics artifacts, and tests aligned in the same change set when behavior changes
- treat `Full precise` as unsimplified geometry
- keep simplification control by zoom band only
- expose session precision control in the UI and support configurable default precision
- do not reintroduce the old live viewport-boundary path as the canonical normal mode

Iteration rule:
- in Phase A, compare at least `pmtiles` and standard vector tiles
- choose the canonical baked artifact format using measurement, not preference
- document the decision and use it for later phases
- Phase A execution record (2026-04-17): `docs/qa/baked_interactive_geometry_phase_a_report_2026-04-17.md`
- current canonical format after Phase A: standard vector tile directory (`z/x/y`)

Performance rule:
- minimum acceptable improvement target is 5x versus current baseline
- stretch target is 20x
- if the stretch target is not reached, document the limiting factor precisely

Output format:
1. Phase executed
2. Summary of changes
3. Measurements before and after
4. Decisions made and why
5. Files changed
6. Residual risks
7. Next recommended phase
