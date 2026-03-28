# Architecture Summary

DocMap is a batch pipeline plus operator control plane plus a separate read-only presentation service.

Primary flows:

- data: `SCP Wiki -> crawler -> snapshots -> extractor -> geocoder -> analytics -> BI -> BigQuery`
- control: `UI/API -> pipeline_commands -> orchestrator -> pipeline_runs/stages/progress/logs`
- presentation: `BI/runtime tables -> presentation API -> presentation UI`

Invariants:

- one active run at a time
- services remain logically separate
- presentation is a separate runtime and stays read-only
- analytics owns derived BI outputs
- startup/runtime truths come from code plus `infra/docker-compose.yml`

Read [ARCHITECTURE.md](D:/Sources/docmap/ARCHITECTURE.md) for the full runtime, deployment, concurrency, and failure model.
