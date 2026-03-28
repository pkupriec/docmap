# Presentation Summary

Presentation is a separate read-only runtime:
- backend: `services/presentation/backend/*`
- frontend: `services/presentation/frontend/*`
- entrypoint: `main_presentation.py`

Key behaviors:
- serves map/document/search APIs
- serves PDF bytes from snapshot blobs
- reads BI/runtime tables only
- does not run pipeline stages or write data

Read full docs:
- [PRESENTATION_ARCHITECTURE.md](PRESENTATION_ARCHITECTURE.md)
- [PRESENTATION_DATA_CONTRACT.md](PRESENTATION_DATA_CONTRACT.md)
- [PRESENTATION_API_SPEC.md](PRESENTATION_API_SPEC.md)
- [PRESENTATION_UX_SPEC.md](PRESENTATION_UX_SPEC.md)
- [PRESENTATION_IMPLEMENTATION_PLAN.md](PRESENTATION_IMPLEMENTATION_PLAN.md)