# Current Phase

Repository baseline:

- phases `0-12` are implemented enough that the pipeline, control plane, and presentation service all exist in code
- the presentation service is already deployed as a separate read-only runtime
- the scheduler exists but is not wired into startup by default

Active task themes:

- phase 13 geometry work is still the main presentation architecture extension
- presentation performance and UX-alignment briefs exist as task-scoped handoffs, not as default preload
- documentation is now split into a compact agent kernel plus full system specs

Practical guidance:

- do not preload `TASKS/` by default
- when working on presentation, load `PRESENTATION.summary.md` first
- when working outside presentation, start from the core summaries
