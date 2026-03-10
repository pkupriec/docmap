# Changelog

All notable repository-level changes are documented here.

## [Unreleased]

### Extraction

- Added Ollama timeout + generation tuning controls:
  - `OLLAMA_TIMEOUT_SECONDS`
  - `OLLAMA_THINK_LEVEL`
  - `OLLAMA_NUM_PREDICT`
- Added extractor model selection via `EXTRACTOR_MODEL` (default `gpt-oss:20b`).
- Extended extractor Ollama success logging with timing/token metadata for performance diagnostics.
- Hardened extraction prompt (`services/extractor/prompts/location_extraction_prompt.md`) with:
  - anti-hallucination constraints
  - stricter normalization/canonicalization guidance
  - precision/confidence guidance
  - deduplication rules
  - few-shot examples

### Documentation

- Rewrote root architecture/project docs to match current code and schema:
  - `README.md`
  - `PROJECT.md`
  - `ARCHITECTURE.md`
  - `SERVICES.md`
  - `PIPELINE.md`
  - `DATA_MODEL.md`
- Added/updated operational documentation package:
  - `docs/CONFIGURATION.md`
  - `docs/DEVELOPMENT.md`
  - `docs/OPERATIONS.md`
  - `docs/VERIFICATION.md`
  - `docs/REPOSITORY_MAP.md`
  - `docs/CONTROL_API.md`

### Clarifications captured in docs

- Stage resume is implemented through control API and orchestrator logic.
- Snapshot storage uses `pdf_blob` (not `pdf_path`).
- Single active run policy and command queue behavior documented as implemented.
- BigQuery export requirements and failure mode documented.
- Scheduler presence documented as partial (module exists, not auto-started).
