# Execution Model

Default behavior:

1. Read `docs/index.md` and follow required reading order.
2. Inspect implementation before editing behavior docs.
3. Load task-scoped docs only when needed.
4. Keep changes minimal and aligned with service/table ownership.

Loading rules:

- For architecture tasks, start from `docs/architecture/*.summary.md`, then full docs.
- For presentation tasks, read `docs/presentation/PRESENTATION.summary.md` and related full specs.
- For operations/API tasks, use `docs/api/*` and `docs/operations/*`.
- Treat `docs/roadmap/*`, `docs/qa/*`, and `docs/archive/*` as contextual, not default authority.

Change rules:

- Keep docs and code aligned in the same change set when behavior changes.
- Do not maintain separate role-specific document variants.
- Do not encode model-specific routing rules in canonical docs.

Verification rules:

- Use cheapest reliable checks first.
- Report what was verified and what was not.
- Do not broaden scope into unrelated cleanup.