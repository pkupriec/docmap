# Current phase

As of 2026-08-26, the project is in refactor verification.

Delivered in this phase:

- versioned on-demand PMTiles replaced the custom full-dataset tile preload;
- MapLibre is the only map renderer;
- presentation is pooled, read-only, and range-efficient;
- PDF thumbnails are generated once and served as WebP;
- pipeline execution has one queue-driven orchestrator with expiring claims;
- BigQuery and obsolete tiling libraries were removed;
- city identity is fixed at the geocoder layer;
- historical documentation was removed from the working tree and retained in Git history.

Exit criteria are the checks and performance budgets in [../operations/VERIFICATION.md](../operations/VERIFICATION.md). Snapshot-history optimization and external warehouse export are explicitly out of scope.
