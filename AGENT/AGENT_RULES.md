# Agent Rules

Compatibility note:

Older prompts may still mention this file first. The canonical entry point is now `AGENT/INDEX.md`.

Core rules:

- preserve the architectural invariants in `AGENT/PROJECT_CONSTITUTION.md`
- follow the loading and change model in `AGENT/EXECUTION_MODEL.md`
- use `AGENT/CURRENT_PHASE.md` for active repository context
- load summaries and full docs only when the task needs them
- keep changes scoped, verified, and synchronized with affected docs
- treat stale or contradictory documentation as a repository defect

Documentation rule:

- treat repository markdown as authoritative execution input unless the task explicitly asks for documentation work
- when a task changes behavior, interfaces, schema, runtime, or operations, update the impacted docs in the same change set
