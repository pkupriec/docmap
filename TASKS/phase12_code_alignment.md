# Phase 12 — Code Alignment Rules

This task clarifies implementation expectations for phase 12.

The user may avoid making manual code edits during review, but the implementing agent must modify code where required.

Mandatory alignment targets:

- backend schemas must match `PRESENTATION_DATA_CONTRACT.md`
- API handlers must match `PRESENTATION_API_SPEC.md`
- frontend state model must match `PRESENTATION_UX_SPEC.md`
- implementation behavior must match `PRESENTATION_ARCHITECTURE.md`
- tests must be updated if they encode obsolete phase 11 payload shapes
- geometry asset ownership must be aligned with service boundaries (analytics generates static polygon assets; presentation consumes them read-only)

The agent is expected to modify Python code, frontend code, and tests where required.

The absence of manual code edits in review does not change the implementation responsibility of the agent.

This is not a documentation-only phase.

Documentation changes without implementation and test alignment are incomplete.

Phase 12 code alignment also includes removal or migration of obsolete phase 11 payload assumptions, especially where tests or schemas still encode preview-text-oriented document cards.
