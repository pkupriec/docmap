# Agent Index

Default coding-agent preload:

1. `AGENT/PROJECT_CONSTITUTION.md`
2. `AGENT/EXECUTION_MODEL.md`
3. `AGENT/CURRENT_PHASE.md`

Read more only when the task requires it.

Authority order:

1. explicit user task
2. `AGENT/PROJECT_CONSTITUTION.md`
3. `AGENT/EXECUTION_MODEL.md`
4. `AGENT/CURRENT_PHASE.md`
5. relevant `*.summary.md`
6. full system specs and task briefs
7. implementation authority in `database/schema.sql` and `infra/docker-compose.yml`

Routing:

- crawler, extractor, geocoder, analytics, control-plane work:
  `ARCHITECTURE.summary.md`, `SERVICES.summary.md`, `PIPELINE.summary.md`, `DATA_MODEL.summary.md`
- presentation work:
  `PRESENTATION.summary.md`, then the specific `PRESENTATION_*` docs
- schema or runtime topology changes:
  `database/schema.sql`, `database/control_plane.sql`, `infra/docker-compose.yml`
- operator or deployment questions:
  `docs/CONFIGURATION.md`, `docs/OPERATIONS.md`, `docs/VERIFICATION.md`
- phase-specific implementation:
  load the relevant file from `TASKS/`

Use `AGENT/doc_router.yaml` for a static lookup map.
