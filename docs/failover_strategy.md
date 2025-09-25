Failover Strategy

Config
- `config/failover_maps.yaml` defines fallback tools per capability as a ranked list.

Behavior
- Planner selects the highest-ranked healthy tool.
- Executor retries a failed phase using the next compatible tool and records the decision.

Audit
- Reroute decisions with reasons should be appended to `state/audit.jsonl`.

