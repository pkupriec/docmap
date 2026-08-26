# DocMap documentation

This directory is intentionally small. Git history contains retired plans and QA reports; only current contracts live here.

Read in this order:

1. [agent/INDEX.md](agent/INDEX.md)
2. [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md)
3. [architecture/DATA_MODEL.md](architecture/DATA_MODEL.md)
4. [architecture/PIPELINE.md](architecture/PIPELINE.md)
5. [api/CONTROL_API.md](api/CONTROL_API.md)
6. [operations/CONFIGURATION.md](operations/CONFIGURATION.md)
7. [operations/OPERATIONS.md](operations/OPERATIONS.md)
8. [operations/VERIFICATION.md](operations/VERIFICATION.md)
9. [roadmap/CURRENT_PHASE.md](roadmap/CURRENT_PHASE.md)

When documentation and implementation disagree, treat that as a defect. Runtime truth is, in order: `database/*.sql`, `infra/docker-compose.yml`, then `services/*`.
