# Verification

## Baseline Checks

1. `docker compose -f infra/docker-compose.yml config`
2. `docker compose -f infra/docker-compose.yml exec -T app pytest -q`
3. `GET http://localhost:8000/api/runs`
4. `GET http://localhost:8080/healthz`
5. `GET http://localhost:8080/api/map/locations`

## Contract Consistency Checks

- Confirm control API includes stage resume endpoint.
- Confirm presentation API includes boundaries, document card, document PDF, and search endpoints.
- Confirm location-documents response includes pagination and scope metadata.
- Confirm schema/docs alignment for canonical geo fields and `bi_document_locations` columns.

## Canonical Refresh Smoke

1. Run `canonical-refresh` profile.
2. Verify report JSON exists at `CANONICAL_REFRESH_REPORT_PATH`.
3. Verify report includes counts for places/aliases/concordances.

## Known Gaps

- scheduler auto-start in app runtime
- authn/authz hardening
- production backup/disaster recovery playbooks