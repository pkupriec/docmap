# Checkpoint 1 Decisions

Date: 2026-03-28

## D1-1: Keep code unchanged, update docs only

Decision: Control backend implementation is internally consistent with tests and SQL contract; only documentation updates were needed.

Rationale: API/orchestrator behavior and test assertions align; mismatches were documentation omissions.

## D1-2: Treat orchestrator behavior as contract for control docs

Decision: Document queue/defer/cancel semantics from `services/control/orchestrator.py` as runtime truth.

Rationale: control API enqueues commands; orchestrator determines real lifecycle semantics.

## D1-3: Define SSE cursor semantics around logs

Decision: Document that `last_event_id` is a numeric `pipeline_logs.id` cursor, not a strict replay cursor for synthetic events.

Rationale: implementation advances cursor only from log rows and emits synthetic ids for other event classes.
