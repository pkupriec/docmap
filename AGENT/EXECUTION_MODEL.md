# Execution Model

Coding agents optimize for small-context execution.

Default behavior:

1. read the kernel in `AGENT/`
2. inspect code before changing it
3. load only the summaries and full docs needed for the active task
4. load phase briefs from `TASKS/` only when the task is phase-specific

Loading rules:

- start with `*.summary.md` for core architecture
- open the full doc when a summary is insufficient or the task touches that subsystem directly
- use `docs/` for operator, config, verification, or repository-navigation questions
- keep historical or superseded rationale out of default preload

Change rules:

- prefer the smallest change that preserves repository invariants
- keep service ownership and table ownership intact
- treat markdown as authoritative execution input unless the user explicitly asks for documentation work
- when behavior, schema, runtime, or interfaces change, sync the affected docs in the same change set

Verification rules:

- verify the touched layer with the cheapest reliable check first
- report exactly what was verified and what was not
- do not broaden a task into unrelated cleanup
