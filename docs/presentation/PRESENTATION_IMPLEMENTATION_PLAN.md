# Presentation Implementation Plan (Historical + Current State)

This file captures historical phase planning and current delivery posture.

## Delivered

- Separate presentation runtime and container
- Read-only map/document API
- Frontend map exploration UI
- Search endpoint and UI flow
- PDF modal/preview workflow
- Rank-aware map rendering behavior

## Current Constraints

- Data quality and geometry coverage depend on upstream BI/boundary inputs.
- Presentation remains intentionally read-only.
- Behavior contracts must stay aligned with `services/presentation/backend/*`.

## Ongoing Improvement Areas

- geometry coverage quality
- UX clarity and performance
- query optimization for large BI datasets
- stronger verification coverage

## Governance Rule

When behavior changes, update in the same change set:
- `PRESENTATION_ARCHITECTURE.md`
- `PRESENTATION_DATA_CONTRACT.md`
- `PRESENTATION_API_SPEC.md`
- relevant tests