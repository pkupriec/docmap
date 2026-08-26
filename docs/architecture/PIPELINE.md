# Pipeline

The fixed stage order is:

1. `crawl`
2. `extract`
3. `geocode`
4. `analytics`
5. `export`

The API and APScheduler call `PipelineCommandService`, which only inserts commands. `ControlOrchestrator` atomically claims commands and is the sole execution engine.

Command claims use `claim_token`, `claimed_at`, and `lease_expires_at`. Expired work can be reclaimed; a stale token cannot complete or fail a command owned by another worker. Deferral releases the lease and returns the command to `pending`.

Retry parameters merge under `parameters_json.options`. Stage retry resets the selected stage and downstream stages. Resume continues from stored progress when supported.

Scheduler runs enqueue `full_pipeline` or `incremental` with `process_unprocessed_only=true`; they never call stages directly.

The export stage is provider-neutral. With no registered `DOCMAP_EXPORTER`, it succeeds deterministically with zero items. BigQuery is not an active requirement.

The analytics stage rebuilds BI tables, exact boundary rows, and four immutable PMTiles archives: `full_precise`, `balanced_precise`, `simplified`, and `primitive`.
