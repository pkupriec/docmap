# Project constitution

These invariants require explicit user approval to change:

- Stage order is `crawl -> extract -> geocode -> analytics -> export`.
- The control API and scheduler enqueue commands; only the orchestrator executes stages.
- Raw document snapshots are append-only inputs. Derived geo, analytics, and presentation artifacts are rebuildable.
- Table ownership is strict: crawler owns documents/snapshots, extractor owns extraction rows, geocoder owns geo entities/aliases/links, analytics owns `bi_*`, control owns `pipeline_*`.
- Presentation is a separate read-only app and API.
- Docker Compose remains the supported hosting topology.
- Pipeline work commits per item or bounded batch; a single failure must not poison later items.
- Reruns, retries, resumes, and reclaimed leases must be idempotent.

Backward compatibility is not a goal during the current refactor. Preserve behavior and operational topology, not obsolete internal APIs or code shapes.
