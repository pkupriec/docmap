# Pipeline Summary

Stage order for `full_pipeline`:

1. `crawl`
2. `extract`
3. `geocode`
4. `analytics`
5. `export`

Control model:

- commands are enqueued in `pipeline_commands`
- one orchestrator loop executes them
- cancel is cooperative
- resume is encoded as `retry_stage` with `resume=true`

Key invariants:

- incremental processing must remain supported
- item-level failures should be isolated and logged where practical
- analytics rebuilds derived outputs; it does not replace source-stage responsibilities

Read [PIPELINE.md](D:/Sources/docmap/PIPELINE.md) for command semantics, limits, scheduler status, and observability details.
