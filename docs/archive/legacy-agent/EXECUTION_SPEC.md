# Agent Execution Specification

This file remains as an extended compatibility reference. It is not the default preload.

Start here instead:

1. `docs/agent/INDEX.md`
2. `docs/agent/PROJECT_CONSTITUTION.md`
3. `docs/agent/EXECUTION_MODEL.md`
4. `docs/roadmap/CURRENT_PHASE.md`

## Repository Facts

- DocMap maps documents to real-world locations mentioned in document text
- the core pipeline is `crawl -> extract -> geocode -> analytics -> export`
- services remain logically separate
- presentation is a separate read-only service over BI/runtime data
- hierarchy fallback remains `city -> region -> country`

## Authority Model

When documents overlap, use this order:

1. explicit user task
2. agent kernel in `AGENT/`
3. relevant `*.summary.md`
4. full system specs
5. scoped task briefs from `docs/roadmap/phases/`
6. schema/runtime authority in `database/schema.sql`, `database/control_plane.sql`, and `infra/docker-compose.yml`

## Loading Model

- read summaries before full docs when possible
- read phase briefs only when the task is phase-specific
- use `docs/` for operator, deployment, verification, or repository-map questions
- use `docs/agent/doc_router.yaml` for static task-to-doc routing

## Non-Negotiable Constraints

- snapshots are immutable historical records
- services do not write foreign tables
- BI and presentation consume derived data rather than mutating source-stage facts
- presentation must not run extraction, normalization, or geocoding logic directly
- `continent` and `ocean` may be rendering ranks but must not silently become fallback targets

## Execution Posture

- inspect code before changing it
- prefer the smallest change that satisfies the task
- verify the touched layer
- update affected docs when the task includes documentation work or when implementation changes behavior
