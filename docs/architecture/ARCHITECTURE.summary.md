# Architecture Summary

DocMap is a pipeline + control plane + separate read-only presentation runtime.

Primary flows:
- data: crawl -> extract -> geocode -> analytics -> export
- control: UI/API -> command queue -> orchestrator -> run state
- presentation: BI tables -> presentation API -> presentation UI

Read [ARCHITECTURE.md](ARCHITECTURE.md) for runtime, failure, and deployment details.