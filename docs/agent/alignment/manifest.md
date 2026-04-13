# Alignment Manifest (Checkpoint 0)

## Objective

Align backend and frontend behavior between documentation and implementation, using code/runtime contracts as source of truth.

## Source-of-Truth Precedence

When docs conflict with implementation, use this order:

1. `database/schema.sql`
2. `database/control_plane.sql`
3. `infra/docker-compose.yml`
4. `services/*` runtime code
5. tests (`tests/*`) as behavioral evidence
6. documentation (`docs/*`) must be updated to match

## Effective Corpus (Filtered)

Excluded from alignment review: `node_modules`, `dist`, `__pycache__`, `.pytest_cache`, generated/vendor output.

- files: 168
- lines: 19,163
- docs: 70 files / 4,802 lines
- services: 60 files / 10,974 lines
- ui: 5 files / 532 lines
- tests: 29 files / 2,283 lines
- database: 3 files / 453 lines
- infra: 1 file / 119 lines

## Checkpoint Strategy (Context-Safe)

Each checkpoint must produce 3 artifacts before moving forward:

- `checkpoint-N-summary.md`: accepted behavior facts
- `checkpoint-N-diffs.md`: doc vs code mismatches
- `checkpoint-N-decisions.md`: resolution choices and rationale

New checkpoint windows should load only:

1. current checkpoint artifacts
2. previous decisions file(s)
3. current domain files + linked tests/docs

## Batch Queue

1. Checkpoint 0: baseline manifest + inventory lock (this file set)
2. Checkpoint 1: control backend + control docs
3. Checkpoint 2: presentation backend + presentation contracts
4. Checkpoint 3: presentation frontend + presentation UX/API docs
5. Checkpoint 4: control UI + control UI docs
6. Checkpoint 5: pipeline/domain services + architecture/operations docs
7. Checkpoint 6: verification run + final consistency sweep

## Completion Definition

Checkpoint 0 is complete when:

- precedence and scope are explicitly fixed
- batch queue is fixed
- no code or docs behavior edits are made yet
- next checkpoint can start without re-scanning whole repo
