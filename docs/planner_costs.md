Cost-Aware Planner Model

Purpose
- Select the cheapest healthy tool per capability and estimate plan cost.

Artifacts
- `lib/planner_cost_model.py`

Inputs
- `config/tools.yaml` → cost_hint, capabilities
- `state/tool_health.json` → current health
- `config/failover_maps.yaml` → optional capability chains

API
```
from lib.planner_cost_model import select_tool_for_capability, estimate_plan_cost

tool = select_tool_for_capability('testing')
cost = estimate_plan_cost([{ 'capability': 'testing' }, { 'capability': 'code_quality' }])
```

Notes
- Uses `cost_hint` until telemetry is available.

