# Event Bus Topics Documentation (MOD-002)

## Overview

The IPT Event Bus provides real-time pub/sub messaging with topic-based routing. This document defines the standard topics and event formats used throughout the system.

## Topic Hierarchy

### Core System Topics

#### Task Management
- **`task.status`** - Task lifecycle events (started, running, completed, failed)
- **`task.created`** - New task creation events
- **`task.cancelled`** - Task cancellation events
- **`task.retry`** - Task retry events

#### Phase Execution
- **`phase.started`** - Phase execution started
- **`phase.progress`** - Phase progress updates
- **`phase.completed`** - Phase execution completed
- **`phase.failed`** - Phase execution failed

#### Cost Tracking
- **`cost.update`** - Real-time cost updates
- **`cost.budget_warning`** - Budget threshold warnings
- **`cost.budget_exhausted`** - Budget exhausted events
- **`cost.estimate`** - Cost estimation events

#### Tool Health
- **`tool.health_changed`** - Tool health status changes
- **`tool.available`** - Tool becomes available
- **`tool.unavailable`** - Tool becomes unavailable
- **`tool.degraded`** - Tool performance degraded

#### Logging
- **`logs.debug`** - Debug level log messages
- **`logs.info`** - Information level log messages
- **`logs.warning`** - Warning level log messages
- **`logs.error`** - Error level log messages

### File Integration Topics
- **`file.*`** - Events from file-based event system
- **`file.progress`** - File-based progress events
- **`file.workflow`** - File-based workflow events

### Legacy Topics
- **`legacy.*`** - Legacy events from existing systems
- **`legacy.broadcast`** - General broadcast messages

## Event Schemas

### Task Status Event
```json
{
  "type": "task_status_changed",
  "topic": "task.status",
  "payload": {
    "task_id": "task-123",
    "status": "running",
    "previous_status": "pending",
    "timestamp": "2025-09-23T12:00:00Z",
    "message": "Task execution started",
    "metadata": {
      "workflow": "PY_EDIT_TRIAGE",
      "user": "system",
      "priority": "normal"
    }
  },
  "timestamp": "2025-09-23T12:00:00Z",
  "source": "executor",
  "correlation_id": "req-456"
}
```

### Phase Progress Event
```json
{
  "type": "phase_progress",
  "topic": "phase.progress",
  "payload": {
    "task_id": "task-123",
    "phase": "code_analysis",
    "progress": 0.75,
    "total_steps": 4,
    "completed_steps": 3,
    "current_step": "Running mypy checks",
    "estimated_completion": "2025-09-23T12:05:00Z"
  },
  "timestamp": "2025-09-23T12:00:00Z",
  "source": "executor"
}
```

### Cost Update Event
```json
{
  "type": "cost_update",
  "topic": "cost.update",
  "payload": {
    "task_id": "task-123",
    "cost_delta": 0.15,
    "total_cost": 2.45,
    "budget_remaining": 7.55,
    "budget_total": 10.00,
    "tool": "claude-cli",
    "operation": "code_analysis",
    "tokens_used": 1500
  },
  "timestamp": "2025-09-23T12:00:00Z",
  "source": "cost_tracker"
}
```

### Tool Health Event
```json
{
  "type": "tool_health_changed",
  "topic": "tool.health_changed",
  "payload": {
    "tool_name": "aider",
    "status": "degraded",
    "previous_status": "healthy",
    "latency_ms": 5000,
    "error_message": "High response latency detected",
    "health_score": 0.6,
    "capabilities": ["ai_editing", "code_generation"]
  },
  "timestamp": "2025-09-23T12:00:00Z",
  "source": "tool_registry"
}
```

### Log Event
```json
{
  "type": "log_message",
  "topic": "logs.warning",
  "payload": {
    "level": "WARNING",
    "message": "Tool health check timeout for cursor",
    "logger": "tool_registry.health_checker",
    "module": "ipt_tools_ping",
    "function": "check_tool_health",
    "line": 145,
    "context": {
      "tool": "cursor",
      "timeout": 30,
      "attempt": 2
    }
  },
  "timestamp": "2025-09-23T12:00:00Z",
  "source": "logging_adapter"
}
```

## Client Usage Examples

### Publishing Events

#### Python Client (Synchronous)
```python
from lib.ipt_bus_client import EventBusPublisher

publisher = EventBusPublisher()

# Publish task status
publisher.publish_task_status(
    task_id="task-123",
    status="started",
    workflow="PY_EDIT_TRIAGE"
)

# Publish phase progress
publisher.publish_phase_progress(
    task_id="task-123",
    phase="code_analysis",
    progress=0.5
)

# Publish cost update
publisher.publish_cost_update(
    task_id="task-123",
    cost_delta=0.25,
    total_cost=1.75
)
```

#### Python Client (Asynchronous)
```python
import asyncio
from lib.ipt_bus_client import EventBusClient, Event

async def publish_events():
    client = EventBusClient()

    # Create custom event
    event = Event(
        type="custom_event",
        topic="custom.analysis",
        payload={"data": "value"}
    )

    # Publish via REST
    await client.publish_event_rest_async(event)

asyncio.run(publish_events())
```

### Subscribing to Events

#### WebSocket Subscription
```python
import asyncio
from lib.ipt_bus_client import EventBusClient

async def listen_for_events():
    client = EventBusClient()

    # Define event handler
    def handle_task_event(event):
        print(f"Task {event.payload['task_id']} status: {event.payload['status']}")

    # Add handler and connect
    client.add_event_handler("task.status", handle_task_event)
    await client.connect_async(["task.status", "cost.update"])

    # Start listening
    await client.listen_async()

asyncio.run(listen_for_events())
```

#### REST API Queries
```bash
# Get recent events
curl http://127.0.0.1:8765/events?limit=10

# Get events for specific topic
curl http://127.0.0.1:8765/events?topic=task.status&limit=5

# Get available topics
curl http://127.0.0.1:8765/topics

# Get event bus statistics
curl http://127.0.0.1:8765/stats
```

### WebSocket Direct Connection
```javascript
// Connect to all events
const ws = new WebSocket('ws://127.0.0.1:8765/ws');

// Connect to specific topics
const ws = new WebSocket('ws://127.0.0.1:8765/ws?topics=task.status,cost.update');

// Subscribe to additional topics
ws.send(JSON.stringify({
  "action": "subscribe",
  "topics": ["phase.progress", "logs.error"]
}));

// Publish event
ws.send(JSON.stringify({
  "action": "publish",
  "event": {
    "type": "custom_event",
    "topic": "custom.test",
    "payload": {"message": "Hello from WebSocket"}
  }
}));
```

## Integration Points

### Executor Integration
The executor publishes events at key points:
- Task start/completion
- Phase progress updates
- Error conditions
- Cost updates

### Cost Tracker Integration
Real-time cost updates are published to `cost.update` topic with:
- Token usage deltas
- Budget warnings
- Budget exhaustion alerts

### Tool Registry Integration
Health monitoring publishes to `tool.*` topics:
- Health status changes
- Performance degradation alerts
- Tool availability updates

### File Event Integration
Existing file-based events are automatically published to `file.*` topics by the event bus file watcher.

## Monitoring and Debugging

### Event Bus Statistics
- **Total Events**: Number of events processed
- **Events Per Topic**: Distribution of events by topic
- **Active Connections**: Number of WebSocket connections
- **Events Per Second**: Throughput metrics
- **Buffer Size**: Current event buffer utilization

### Health Monitoring
- **Latency**: Average event delivery latency
- **Connection Stability**: WebSocket connection health
- **Event Loss**: Dropped events due to buffer overflow
- **Topic Activity**: Most active topics

### Debugging Tools
```bash
# Monitor real-time events
wscat -c ws://127.0.0.1:8765/ws

# Monitor specific topic
wscat -c ws://127.0.0.1:8765/ws?topics=task.status

# Check event bus health
curl http://127.0.0.1:8765/health

# Get detailed statistics
curl http://127.0.0.1:8765/stats | jq
```

## Best Practices

### Topic Design
1. Use hierarchical naming (e.g., `task.status`, `tool.health`)
2. Keep topics focused and specific
3. Avoid overly granular topics that create noise
4. Use consistent naming conventions

### Event Publishing
1. Include comprehensive context in payload
2. Use correlation IDs for request tracing
3. Set appropriate event types for filtering
4. Include timestamps for ordering

### Event Consumption
1. Filter events at the topic level
2. Handle events asynchronously to avoid blocking
3. Implement proper error handling for event processing
4. Use wildcard subscriptions sparingly

### Performance Considerations
1. **Batch Processing**: Group related events when possible
2. **Buffer Management**: Monitor buffer utilization
3. **Connection Pooling**: Reuse WebSocket connections
4. **Topic Filtering**: Subscribe only to needed topics
5. **Event Size**: Keep payloads reasonable (< 1MB)

## Future Enhancements

### Planned Features (Future MODs)
- **Message Persistence**: Durable event storage
- **Event Replay**: Historical event playback
- **Dead Letter Queue**: Failed event handling
- **Rate Limiting**: Publisher throttling
- **Schema Validation**: Event format enforcement
- **Metrics Export**: Prometheus integration
- **Authentication**: Event bus access control
