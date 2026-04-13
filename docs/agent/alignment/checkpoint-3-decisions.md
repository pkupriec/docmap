# Checkpoint 3 Decisions

Date: 2026-03-28

## D3-1: Frontend network behavior is authoritative for UX performance notes

Decision: Document startup boundaries fetch as lite mode (`lite=1`) rather than full payload.

Rationale: frontend API client defines actual request contract and startup path.

## D3-2: Preserve UX state semantics as currently implemented

Decision: Keep existing UX state descriptions that match current code (search precedence, modal/escape behavior, declutter links, geometry thresholds).

Rationale: reviewed implementation and behavior are consistent; no corrective code change needed in this checkpoint.
