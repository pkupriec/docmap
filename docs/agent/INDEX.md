# Agent entrypoint

Read [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md), then follow the reading order in [../index.md](../index.md).

Working rules:

- Preserve user work and inspect the worktree before edits.
- Keep changes inside the service that owns the affected tables.
- Use the control command queue for pipeline execution.
- Keep presentation read-only.
- Add or update focused tests with behavior changes.
- Update canonical docs in the same change when a contract changes.
- Generated artifacts, dependency metadata, and historical handoffs do not belong in source control.
