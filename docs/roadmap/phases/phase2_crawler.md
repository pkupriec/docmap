# Phase 2 - SCP Crawler

Goal: fetch SCP wiki pages and persist immutable snapshots.

## Tasks

1. Implement SCP URL generator for `scp-001` through `scp-7999`.
2. Implement HTML downloader for `https://scp-wiki.wikidot.com/scp-XXXX`.
3. Parse article HTML with BeautifulSoup.
4. Extract article body text and remove non-content UI elements:
   - navigation
   - sidebar
   - rating/edit/meta/footer blocks
5. Persist `raw_html`.
6. Generate `clean_text` suitable for extraction.
7. Generate PDF snapshot (wkhtmltopdf or equivalent).
8. Insert snapshot record into `document_snapshots`.
9. Add retry logic for HTTP and parsing failures (3 retries, exponential backoff).
10. Add rate limiting (minimum 1 request/second with jitter).
11. Implement incremental behavior with deterministic snapshot creation:
    - compute `clean_text_hash = sha256(clean_text)`
    - compare with latest snapshot hash computed on read (`sha256(latest.clean_text)`)
    - create a new snapshot only if hash changed or resnapshot explicitly requested

## Acceptance Criteria

- Crawler can process a single URL and a numeric range mode.
- Unchanged documents do not produce new snapshot rows in normal incremental runs.
- Failed documents are logged and skipped without aborting the batch.
- `clean_text` excludes obvious UI noise and retains narrative/addenda content.
