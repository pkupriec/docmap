# Repository Map

## Entrypoints

- control runtime: `main.py`
- presentation runtime: `main_presentation.py`

## Core Directories

- `services/` service implementations
- `database/` SQL schema and seeds
- `infra/` docker-compose and local infra config
- `ui/` control plane frontend
- `tests/` automated tests
- `docs/` canonical documentation tree

## Documentation Structure

- `docs/index.md` canonical entrypoint and reading order
- `docs/agent/` shared agent execution guidance
- `docs/architecture/` project/runtime/data/pipeline docs
- `docs/presentation/` presentation contracts/specs
- `docs/api/` control API + UI spec
- `docs/operations/` runbooks and config
- `docs/reference/` repository/domain references
- `docs/roadmap/` current phase + historical phase docs
- `docs/qa/` historical QA artifacts
- `docs/archive/` deprecated legacy docs

## Runtime Prompt Asset

`services/extractor/prompts/location_extraction_prompt.md` is a runtime implementation input and intentionally stays with service code.