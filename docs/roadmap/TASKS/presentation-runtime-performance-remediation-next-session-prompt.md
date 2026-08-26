# Next Session Prompt: Presentation Runtime Performance Remediation

Copy-paste the prompt below into the next Codex session.

---

Read project context starting from `docs/agent/INDEX.md`.

Then continue the presentation runtime performance remediation work using:
- `docs/roadmap/TASKS/presentation-runtime-performance-remediation-plan.md`
- `docs/roadmap/TASKS/presentation-runtime-performance-remediation-development-prompt.md`

Task for this session:
- Execute **Phase A only** from `presentation-runtime-performance-remediation-plan.md`.
- Do not skip ahead to later phases.

Phase A goals:
- establish a measured performance baseline for the presentation runtime
- add or tighten timing/payload instrumentation around:
  - `/api/map/locations`
  - `/api/map/boundaries`
  - `/api/map/location/{location_id}/documents`
  - `/api/map/document/{document_id}/locations`
  - `/api/search`
- add local verification guidance for startup timing, boundary request counts, location-documents timing, and search timing
- align canonical schema/docs with runtime assumptions for `bi_admin_boundaries` envelope columns and indexes:
  - `min_lon`
  - `min_lat`
  - `max_lon`
  - `max_lat`
- audit hot-path presentation indexes and call out missing ones

Important constraints:
- keep behavior deterministic
- keep presentation runtime read-only
- keep docs, schema, migrations, and code aligned in the same change set
- do not broaden scope into unrelated cleanup
- explicitly identify anything that should be baked/precomputed ahead instead of kept in runtime

Expected output:
1. Summary of Phase A changes
2. Files changed
3. Measured baseline / verification results
4. Schema/runtime alignment findings
5. Items recommended to move out of runtime and bake ahead
6. Residual risks
7. Recommended next phase

If you find that a runtime assumption exists only in migrations but not in canonical schema/docs, fix that in this same Phase A change set.

---
