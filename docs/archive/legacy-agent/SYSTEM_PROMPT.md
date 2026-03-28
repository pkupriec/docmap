# System Prompt Compatibility Note

This repository now uses a small agent kernel plus full system specs.

Start with:

- `docs/agent/INDEX.md`
- `docs/agent/PROJECT_CONSTITUTION.md`
- `docs/agent/EXECUTION_MODEL.md`
- `docs/roadmap/CURRENT_PHASE.md`

Core concept:

- DocMap maps documents to locations mentioned in their text
- the architecture is implementation-first, not redesign-first
- load additional docs only when the active task requires them
