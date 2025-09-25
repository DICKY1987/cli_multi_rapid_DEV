Health Policies & Circuit Breakers

Inputs
- Ping results from `scripts/ipt_tools_ping.py` → `state/tool_health.json`
- Historical pings → `state/tool_health_history.jsonl`
- Recent failures from execution logs

Scoring (example)
- `score = availability * success_rate * latency_factor`
- See `lib/health_scoring.py` for the concrete model and thresholds.

Circuit States
- Closed → normal; Open → exclude tool; Half-open → test after cooldown

Planner/Executor Integration
- Planner excludes tools below threshold.
- Executor avoids unstable tools and retries when half-open allows.

