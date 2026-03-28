# Presentation Summary

The presentation layer is a separate read-only service composed of `services/presentation/backend/*` and `services/presentation/frontend/*`.

Runtime behavior:

- backend reads BI/runtime tables and serves map/document/PDF APIs
- frontend becomes ready only after startup requests complete
- search is API-backed
- PDF viewing is iframe-based

Map invariants:

- hierarchy fallback remains `city -> region -> country`
- `city` may render as polygon only when a boundary exists and zoom is high enough; otherwise it is a point
- `admin_region`, `country`, `continent`, and `ocean` use polygons when boundaries exist, otherwise points
- missing-boundary non-city points remain red

Read these full docs when touching presentation:

- [PRESENTATION_ARCHITECTURE.md](D:/Sources/docmap/PRESENTATION_ARCHITECTURE.md)
- [PRESENTATION_DATA_CONTRACT.md](D:/Sources/docmap/PRESENTATION_DATA_CONTRACT.md)
- [PRESENTATION_API_SPEC.md](D:/Sources/docmap/PRESENTATION_API_SPEC.md)
- [PRESENTATION_UX_SPEC.md](D:/Sources/docmap/PRESENTATION_UX_SPEC.md)
- [PRESENTATION_IMPLEMENTATION_PLAN.md](D:/Sources/docmap/PRESENTATION_IMPLEMENTATION_PLAN.md)
