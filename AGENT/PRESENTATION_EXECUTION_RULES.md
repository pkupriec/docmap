# PRESENTATION_EXECUTION_RULES.md

The agent must follow the architecture documents strictly.

The agent must not redesign the architecture.

---

# Mandatory Reading Order

1. EXECUTION_SPEC.md
2. ARCHITECTURE.md
3. DATA_MODEL.md
4. SERVICES.md
5. PRESENTATION_ARCHITECTURE.md
6. PRESENTATION_DATA_CONTRACT.md
7. PRESENTATION_UX_SPEC.md
8. PRESENTATION_API_SPEC.md

---

# Forbidden Changes

The agent must not:

introduce message brokers
introduce background workers
modify operational tables
modify extraction logic

---

# Implementation Strategy

The agent must:

implement backend first
implement API
implement frontend
deploy service

---

# Determinism

Given identical BI tables, the API responses must remain identical.

The agent must not introduce non-deterministic behavior.