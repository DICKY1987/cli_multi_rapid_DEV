Event Bus Topics

This repository provides two complementary event systems:

- HTTP + WebSocket hub (FastAPI) at `services/event_bus/main.py`
- In-process WebSocket broadcaster utilities under `src/websocket/`

Key endpoints:
- `GET /health` → liveness probe
- `GET /metrics` → Prometheus (optional)
- `GET /events/recent?limit=N` → last N events (<= 200)
- `WS /ws` → broadcast channel (server fan-outs JSON messages)
- `POST /publish` → publish JSON payload which is fanned out to WS clients

Topic conventions for payloads (field `type`):
- `task.status` → task lifecycle
- `phase.progress` → phase progress updates
- `cost.update` → cost deltas and budget remaining
- `logs.debug` → debug/info logs

WebSocket payload example:
```
{
  "type": "phase.progress",
  "workflow_id": "wf-123",
  "phase": "lint",
  "pct": 42,
  "ts": "2025-01-01T00:00:00Z"
}
```

Related code:
- `lib/ipt_bus_client.py` – minimal HTTP publisher
- `src/websocket/event_broadcaster.py` – in-process broadcasting helpers

