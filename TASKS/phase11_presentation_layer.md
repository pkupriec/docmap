# Phase 11 — Presentation Layer

## Goal

Implement a read-only presentation layer for interactive spatial exploration of SCP documents and locations.

The presentation layer must consume BI tables only.

It must provide:
- presentation API
- interactive map UI
- document/location exploration workflow

The presentation layer must be implemented as a separate service module with its own frontend and backend.

It must not be merged into the control plane UI or control plane container.

Expected compose service:
- presentation

## Authoritative Inputs

The agent must read and follow:

- ARCHITECTURE.md
- SERVICES.md
- DATA_MODEL.md
- PRESENTATION_ARCHITECTURE.md
- PRESENTATION_DATA_CONTRACT.md
- PRESENTATION_UX_SPEC.md
- PRESENTATION_API_SPEC.md
- PRESENTATION_IMPLEMENTATION_PLAN.md
- AGENT/PRESENTATION_EXECUTION_RULES.md
- implementation inside dedicated presentation module trees (`services/presentation/backend`, `services/presentation/frontend`)

## Scope

Phase 11 includes:

- BI extensions needed for presentation
- read-only presentation API
- map-first desktop UI
- hover and pinned selection
- document cards with preview text
- map-to-panel and panel-to-map synchronization
- density overlay support if it does not destabilize MVP
- dedicated presentation frontend application
- dedicated presentation backend application
- separate presentation container build

## Out of Scope

Do not implement in this phase:

- search
- mobile-first UI
- polygon/area rendering
- authentication
- user preferences
- writeback/edit workflows
- merging presentation UI into the control plane UI
- deploying presentation inside the control plane container

## Required Outputs

- BI schema updates
- tests for BI projections
- presentation backend module
- presentation frontend implementation
- compose integration
- documentation refresh
- separate presentation frontend module tree
- separate presentation backend module tree
- dedicated Docker build for presentation service

## Ordered Work Plan

1. finalize BI contract changes
2. update schema and BI rebuild logic
3. implement backend query layer
4. implement API endpoints
5. implement UI shell
6. integrate map rendering
7. implement hover/pin/reset behavior
8. implement document cards and line highlighting
9. add tests
10. update docs

## Acceptance Criteria

- presentation reads BI tables only
- no writes occur outside analytics-owned BI rebuild logic
- UI supports hover preview and pinned selection
- reset works via empty-map click, Esc, and Clear button
- document cards open source links in new tab
- point geometry rendering works for target dataset size
- implementation remains consistent with architecture docs
- implementation preserves the existing repository UI architecture
- no search functionality is introduced in MVP
- hierarchy fallback is resolved through BI/API logic, not frontend heuristics
- presentation frontend is isolated from the control plane frontend
- presentation service builds as a separate container
- control plane container is not modified to host presentation runtime
