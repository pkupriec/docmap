# Coding Conventions

## Language and Runtime

- Primary language: Python
- Target version: Python 3.11+

## Structure

- Keep service boundaries explicit under `services/`.
- Prefer small focused modules over monolithic files.
- Keep shared concerns in `services/common/`.

## Style

- Follow PEP 8.
- Use type hints on public functions and data models.
- Add concise structured logs with actionable context.

## Error Handling

- Isolate item-level failures when possible.
- Avoid crashing whole stages for single-item errors.
- Record errors in pipeline logs/progress.

## Configuration

- Use environment variables for runtime behavior.
- Do not hardcode machine-local paths or endpoints.

## Docs Synchronization

When behavior changes, update related docs in the same change set:
- `docs/architecture/*`
- `docs/presentation/*` (if presentation-facing)
- `docs/api/*` (if API-facing)
- `docs/operations/*` (if runtime/ops-facing)