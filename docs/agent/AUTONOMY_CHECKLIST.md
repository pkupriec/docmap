# Autonomous Development Checklist

## Baseline Gates

- [ ] Requested behavior is confirmed in implementation files.
- [ ] Table ownership and service boundaries remain intact.
- [ ] Docs touched by behavior changes are updated in same change set.
- [ ] Fast verification commands are run and results reported.

## Pipeline and Data Gates

- [ ] Stage order and command semantics remain unchanged unless explicitly requested.
- [ ] Resume/retry behavior remains deterministic.
- [ ] `bi_*` projections remain rebuildable from operational facts.
- [ ] Presentation remains read-only.

## Ops and Runtime Gates

- [ ] Compose/runtime docs match `infra/docker-compose.yml`.
- [ ] New env vars are documented in `docs/operations/CONFIGURATION.md`.
- [ ] API changes are reflected in `docs/api/CONTROL_API.md` and OpenAPI artifact.

## Out-of-Scope Guardrails

- [ ] No silent architecture redesign.
- [ ] No hidden role-specific documentation variants.
- [ ] No machine-specific absolute paths in canonical docs.