# Phase 7 - BigQuery Export

Goal: export BI tables from Postgres to BigQuery.

## Required Configuration

- `GCP_PROJECT_ID`
- `BIGQUERY_DATASET` (default: `docmap_mvp`)
- `BIGQUERY_LOCATION` (default: `US`)
- `GOOGLE_APPLICATION_CREDENTIALS` (service-account JSON path)

## Tasks

1. Create BigQuery dataset `${GCP_PROJECT_ID}.${BIGQUERY_DATASET}`.
2. Implement exporter for:
   - `bi_documents` -> `bi_documents`
   - `bi_locations` -> `bi_locations`
   - `bi_document_locations` -> `bi_document_locations`
3. Implement schema mapping from Postgres types to BigQuery types.
4. Implement full export mode (`WRITE_TRUNCATE`).
5. Implement incremental export mode using staging tables + `MERGE` on primary keys.
6. Emit structured export logs with row counts and job IDs.

## Acceptance Criteria

- Full export creates/updates all three target tables in BigQuery.
- Incremental export updates only changed rows by key.
- Export failures do not mutate Postgres BI tables.
