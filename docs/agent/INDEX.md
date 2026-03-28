# Agent Index

All agents use the same complete knowledge base.

Default preload:
1. `docs/agent/PROJECT_CONSTITUTION.md`
2. `docs/agent/EXECUTION_MODEL.md`
3. `docs/roadmap/CURRENT_PHASE.md`

Authority order:
1. explicit user task
2. `docs/agent/PROJECT_CONSTITUTION.md`
3. `docs/agent/EXECUTION_MODEL.md`
4. `docs/index.md` required reading order
5. implementation truth in code/schema/compose

Use `docs/agent/doc_router.yaml` as a static lookup map.