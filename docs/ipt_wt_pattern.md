IPT/WT Workflow Pattern

Overview
- IPT (Interface & Planning Tool) handles planning, verification, and git operations.
- WT (Work Tools) handle implementation, testing, and docs.

Quick Start
- Run scaffolded pattern with budget-aware routing and generate a decision artifact:

```bash
cli-orchestrator run-ipt-wt --request "Improve code quality" --budget 3000
# See artifacts/ipt-wt/decision.json
```

Workflow File
- See `.ai/workflows/ipt_wt_workflow.yaml` for roles, phases, and tasks.

Routing
- Router prefers AI adapters for `ipt` within budget, deterministic tools for `wt`.
- Falls back to cheapest deterministic adapter if budget is insufficient.
