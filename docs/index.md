# DocMap Documentation

This is the canonical documentation entrypoint for humans and autonomous agents.

If documentation conflicts with implementation, treat this as a documentation defect and follow:
1. `database/schema.sql`
2. `database/control_plane.sql`
3. `infra/docker-compose.yml`
4. `services/*`

## Required Reading Order

1. [architecture/PROJECT.md](architecture/PROJECT.md)
2. [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md)
3. [architecture/SERVICES.md](architecture/SERVICES.md)
4. [architecture/DATA_MODEL.md](architecture/DATA_MODEL.md)
5. [architecture/PIPELINE.md](architecture/PIPELINE.md)
6. [presentation/PRESENTATION_ARCHITECTURE.md](presentation/PRESENTATION_ARCHITECTURE.md)
7. [presentation/PRESENTATION_DATA_CONTRACT.md](presentation/PRESENTATION_DATA_CONTRACT.md)
8. [presentation/PRESENTATION_API_SPEC.md](presentation/PRESENTATION_API_SPEC.md)
9. [agent/PROJECT_CONSTITUTION.md](agent/PROJECT_CONSTITUTION.md)
10. [agent/EXECUTION_MODEL.md](agent/EXECUTION_MODEL.md)
11. [api/CONTROL_API.md](api/CONTROL_API.md)
12. [operations/CONFIGURATION.md](operations/CONFIGURATION.md)
13. [operations/OPERATIONS.md](operations/OPERATIONS.md)
14. [operations/VERIFICATION.md](operations/VERIFICATION.md)
15. [roadmap/CURRENT_PHASE.md](roadmap/CURRENT_PHASE.md)

## Optional Task-Scoped Reading

- [roadmap/phases/](roadmap/phases/)
- [roadmap/handoffs/](roadmap/handoffs/)
- [qa/](qa/)
- [archive/legacy-agent/](archive/legacy-agent/)

## Directory Map

- `docs/agent` shared execution rules for all agents
- `docs/architecture` system structure, service boundaries, data model, pipeline
- `docs/presentation` presentation runtime and API contracts
- `docs/api` control plane API and UI spec
- `docs/operations` configuration, development, runbook, verification
- `docs/reference` repository and domain context references
- `docs/roadmap` current phase, historical phases, and handoffs
- `docs/qa` historical QA artifacts
- `docs/archive` deprecated legacy docs kept for traceability