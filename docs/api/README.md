# CLI Orchestrator API Documentation

Welcome to the CLI Orchestrator API documentation. This directory contains comprehensive API specifications, examples, and guides for integrating with the CLI Orchestrator HTTP services.

## Overview

The CLI Orchestrator provides enterprise-grade HTTP APIs for:

- **Workflow Execution**: Execute schema-validated workflows with monitoring
- **Artifact Management**: Access and download workflow artifacts
- **Security & Authentication**: JWT tokens and API key management
- **Metrics & Monitoring**: Performance analytics and health checks
- **System Management**: Service configuration and status

## Quick Start

### 1. Authentication

Create an API key:

```bash
curl -X POST http://localhost:8080/api/v1/auth/api-key \
  -H "Content-Type: application/json" \
  -d '{"description": "My API key"}'
```

### 2. Execute a Workflow

```bash
curl -X POST http://localhost:8080/api/v1/workflows/execute \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/PY_EDIT_TRIAGE.yaml",
    "files": "src/**/*.py",
    "max_tokens": 50000
  }'
```

### 3. Check Service Health

```bash
curl http://localhost:8080/api/v1/health
```

## Documentation Structure

```
docs/api/
├── README.md              # This file
├── openapi.yaml           # OpenAPI 3.0 specification
├── examples/              # Request/response examples
│   ├── workflow-execution.md
│   ├── authentication.md
│   └── error-handling.md
├── guides/                # Integration guides
│   ├── getting-started.md
│   ├── authentication.md
│   ├── rate-limiting.md
│   └── webhook-integration.md
└── schemas/               # JSON schemas for validation
    ├── workflow-request.json
    ├── workflow-response.json
    └── error-response.json
```

## API Reference

### Base URL

- Development: `http://localhost:8080/api/v1`
- Production: `https://api.cli-orchestrator.local/api/v1`

### Authentication

The API supports two authentication methods:

1. **API Keys** (Recommended for programmatic access)
   - Header: `X-API-Key: your-api-key`
   - Long-lived, can be managed per user

2. **JWT Tokens** (For user sessions)
   - Header: `Authorization: Bearer your-jwt-token`
   - Short-lived, includes user permissions

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/workflows/execute` | POST | Execute a workflow |
| `/workflows/{name}/status` | GET | Get workflow status |
| `/artifacts` | GET | List artifacts |
| `/artifacts/{path}` | GET | Download artifact |
| `/auth/api-key` | POST | Create API key |
| `/metrics/summary` | GET | Get metrics summary |
| `/health` | GET | Health check |
| `/info` | GET | Service information |

### Response Format

All API responses follow a consistent format:

**Success Response:**

```json
{
  "success": true,
  "data": { ... },
  "execution_time": 0.123
}
```

**Error Response:**

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": { ... },
  "request_id": "req_abc123"
}
```

### Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `429` - Rate Limited
- `500` - Internal Server Error
- `503` - Service Unavailable

## Rate Limiting

API requests are rate limited per user:

- **General API calls**: 60 requests/minute
- **Workflow executions**: 10 concurrent workflows
- **Authentication**: 5 attempts/minute

Rate limit headers:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1609459200
```

## Error Handling

### Common Error Codes

| Code | Description | Resolution |
|------|-------------|-----------|
| `validation_error` | Request validation failed | Check request format |
| `unauthorized` | Authentication required | Provide valid API key/token |
| `forbidden` | Insufficient permissions | Check user roles |
| `rate_limited` | Rate limit exceeded | Wait and retry |
| `workflow_not_found` | Workflow file not found | Verify workflow path |
| `execution_failed` | Workflow execution failed | Check workflow configuration |

### Retry Strategy

For transient errors (429, 5xx), implement exponential backoff:

```python
import time
import requests

def api_request_with_retry(url, headers, data, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(url, headers=headers, json=data)

        if response.status_code < 500:
            return response

        wait_time = 2 ** attempt  # Exponential backoff
        time.sleep(wait_time)

    return response
```

## Security Best Practices

### API Key Security

1. **Store securely**: Use environment variables or secret management
2. **Rotate regularly**: Create new keys and revoke old ones
3. **Limit scope**: Use least-privilege principle
4. **Monitor usage**: Track API key usage patterns

### Request Security

1. **Use HTTPS**: Always use encrypted connections in production
2. **Validate input**: Sanitize all workflow parameters
3. **Rate limiting**: Implement client-side rate limiting
4. **Error handling**: Don't expose sensitive information in errors

## SDK and Libraries

### Python SDK

```python
from cli_orchestrator import Client

client = Client(
    base_url="https://api.cli-orchestrator.local/api/v1",
    api_key="your-api-key"
)

# Execute workflow
result = client.workflows.execute(
    workflow_file=".ai/workflows/PY_EDIT_TRIAGE.yaml",
    files="src/**/*.py",
    max_tokens=50000
)

if result.success:
    print(f"Workflow completed: {result.artifacts}")
else:
    print(f"Workflow failed: {result.error}")
```

### JavaScript/Node.js

```javascript
const { CliOrchestratorClient } = require('@cli-orchestrator/client');

const client = new CliOrchestratorClient({
  baseUrl: 'https://api.cli-orchestrator.local/api/v1',
  apiKey: 'your-api-key'
});

// Execute workflow
const result = await client.workflows.execute({
  workflowFile: '.ai/workflows/PY_EDIT_TRIAGE.yaml',
  files: 'src/**/*.py',
  maxTokens: 50000
});

if (result.success) {
  console.log(`Workflow completed: ${result.artifacts}`);
} else {
  console.log(`Workflow failed: ${result.error}`);
}
```

## Webhook Integration

Configure webhooks to receive workflow completion notifications:

### Setup Webhook

```bash
curl -X POST http://localhost:8080/api/v1/webhooks \
  -H "X-API-Key: your-api-key" \
  -d '{
    "url": "https://your-app.com/webhooks/cli-orchestrator",
    "events": ["workflow.completed", "workflow.failed"],
    "secret": "your-webhook-secret"
  }'
```

### Webhook Payload

```json
{
  "event": "workflow.completed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "execution_id": "exec_abc123",
    "workflow_name": "PY_EDIT_TRIAGE",
    "success": true,
    "artifacts": ["artifacts/diagnostics.json"],
    "tokens_used": 1250,
    "execution_time": 12.5
  }
}
```

## Support and Resources

- **OpenAPI Spec**: [`openapi.yaml`](openapi.yaml) - Full API specification
- **Examples**: [`examples/`](examples/) - Request/response examples
- **Guides**: [`guides/`](guides/) - Integration guides
- **Issues**: Report bugs and feature requests
- **Community**: Join our developer community

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-01 | Initial API release |
| 1.1.0 | 2024-02 | Added webhook support |
| 1.2.0 | 2024-03 | Enhanced security features |

For the latest updates, see the [CHANGELOG](CHANGELOG.md).
