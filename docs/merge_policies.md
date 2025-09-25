Merge Policies

Objective
- Select and execute an appropriate merge strategy based on conflict complexity, tool capabilities, and cost policy.

Implementation
- `lib/automated_merge_strategy.py` contains analysis, selection, and execution.
- `lib/merge_strategy.py` provides a stable facade for integrations.

Audit & Cost
- Decisions and outcomes are recorded in `state/audit.jsonl` with `merge_strategy` metadata.

