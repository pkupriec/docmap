# Checkpoint 2 Decisions

Date: 2026-03-28

## D2-1: Differentiate not-found contracts by endpoint family

Decision: Document endpoint-specific not-found semantics instead of one shared rule.

Rationale: presentation backend intentionally uses `404` for single-document resources and `200` empty payload for unresolved location scope.

## D2-2: Preserve dual search semantics (validation vs effective matching)

Decision: Keep docs explicit that API validation allows short queries while repository intentionally returns empty results for trimmed queries under 3 chars.

Rationale: this reflects current code and existing UX behavior assumptions.

## D2-3: Treat hierarchy traversal as backend scope contract

Decision: Replace fixed non-city rank ladders with hierarchy-descendant semantics in architecture/data docs.

Rationale: repository logic applies explicit rank filter only for city and relies on BI hierarchy content for non-city scope shape.
