# Documentation Context Restructure

## Purpose

This note explains the documentation split introduced for two model roles:

- coding agents with small context windows
- general models that can absorb the full repository specification

## Audit Findings

The repository already had a usable full-system spec in the top-level `*.md` files, but the agent layer had four problems:

1. core architecture and workflow rules were repeated across `AGENT_RULES.md`, `EXECUTION_SPEC.md`, `DEV_WORKFLOW.md`, `ANTI_PATTERNS.md`, `SYSTEM_PROMPT.md`, and `PRESENTATION_EXECUTION_RULES.md`
2. authority ordering was unclear, especially when phase briefs, architecture docs, and agent files overlapped
3. several files mixed stable architectural constraints with phase-specific execution prompts
4. the default agent read path was too large and too repetitive for small-context coding agents

## New Layering

### 1. Agent kernel

The default preload is now:

- `docs/agent/PROJECT_CONSTITUTION.md`
- `docs/agent/EXECUTION_MODEL.md`
- `docs/roadmap/CURRENT_PHASE.md`

`docs/agent/INDEX.md` explains the order and routing. This kernel is the small, high-signal entry point for coding agents.

### 2. System specification

The full repository specification remains in:

- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/SERVICES.md`
- `docs/architecture/PIPELINE.md`
- `docs/architecture/DATA_MODEL.md`
- `PRESENTATION_*`

Concise invariant-focused summaries were added so coding agents can load less context first:

- `ARCHITECTURE.summary.md`
- `SERVICES.summary.md`
- `PIPELINE.summary.md`
- `DATA_MODEL.summary.md`
- `PRESENTATION.summary.md`

### 3. Task briefs

`docs/roadmap/phases/` remains available as scoped execution material, but it is no longer part of the default preload.

### 4. Operations/reference

`docs/` remains the operator and verification layer and is loaded on demand.

## Canonical Authority

The intended order is now:

1. explicit user task
2. agent kernel in `AGENT/`
3. relevant summaries
4. full system specs
5. scoped task briefs
6. implementation authority in schema/runtime files

## Duplication Reduction

Important rules were moved into canonical locations:

- global invariants and table/service boundaries -> `docs/agent/PROJECT_CONSTITUTION.md`
- coding-agent loading and change behavior -> `docs/agent/EXECUTION_MODEL.md`
- active repository phase context -> `docs/roadmap/CURRENT_PHASE.md`

Legacy agent files were retained as extended references, but they now point back to the kernel instead of acting as competing preload material.

## Routing

`docs/agent/doc_router.yaml` provides a small static lookup table for task-to-doc routing. It adds no runtime dependency and is simple enough for autonomous agents to consume directly.

## Remaining Ambiguity

Earlier agent docs used model-version-specific markdown editing rules. The new structure preserves the architectural intent in a role-based way:

- coding agents should treat markdown as authoritative input unless the task explicitly asks for documentation work
- documentation tasks may update impacted markdown files directly
