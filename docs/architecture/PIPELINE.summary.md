# Pipeline Summary

Full pipeline stage order:
1. crawl
2. extract
3. geocode
4. analytics
5. export

Key control semantics:
- commands are queued and applied by orchestrator
- cancellation is cooperative
- stage resume uses `retry_stage` with `resume=true`

Read [PIPELINE.md](PIPELINE.md) for run options, retry/resume rules, and observability.