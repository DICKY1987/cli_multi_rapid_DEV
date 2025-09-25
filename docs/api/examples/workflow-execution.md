# Workflow Execution Examples

This document provides practical examples for executing CLI Orchestrator workflows through the HTTP API.

## Basic Workflow Execution

### Execute Python Triage Workflow

Execute a Python code triage workflow to analyze and fix common issues:

```bash
curl -X POST "http://localhost:8080/api/v1/workflows/execute" \
  -H "X-API-Key: clio_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/PY_EDIT_TRIAGE.yaml",
    "files": "src/**/*.py",
    "lane": "feature/fix-imports",
    "max_tokens": 50000,
    "dry_run": false
  }'
```

**Response:**

```json
{
  "execution_id": "exec_a1b2c3d4e5f6",
  "success": true,
  "error": null,
  "artifacts": [
    "artifacts/diagnostics.json",
    "artifacts/import_fixes.patch",
    "artifacts/type_annotations.patch"
  ],
  "tokens_used": 2150,
  "steps_completed": 4,
  "execution_time_seconds": 18.7,
  "workflow_name": "PY_EDIT_TRIAGE"
}
```

### Dry Run Execution

Preview what a workflow would do without making changes:

```bash
curl -X POST "http://localhost:8080/api/v1/workflows/execute" \
  -H "X-API-Key: clio_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/JS_LINT_FIX.yaml",
    "files": "**/*.js",
    "dry_run": true
  }'
```

**Response:**

```json
{
  "execution_id": "exec_dry_run_123",
  "success": true,
  "error": null,
  "artifacts": [
    "artifacts/lint_preview.json"
  ],
  "tokens_used": 0,
  "steps_completed": 3,
  "execution_time_seconds": 2.1,
  "workflow_name": "JS_LINT_FIX"
}
```

## Advanced Examples

### Custom Parameters

Pass custom parameters to customize workflow behavior:

```bash
curl -X POST "http://localhost:8080/api/v1/workflows/execute" \
  -H "X-API-Key: clio_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/CUSTOM_ANALYSIS.yaml",
    "files": "src/components/**/*.tsx",
    "lane": "feature/component-refactor",
    "max_tokens": 75000,
    "parameters": {
      "analysis_depth": "deep",
      "fix_suggestions": true,
      "output_format": "detailed"
    }
  }'
```

### Large Codebase Processing

Execute workflow on a large codebase with appropriate token limits:

```bash
curl -X POST "http://localhost:8080/api/v1/workflows/execute" \
  -H "X-API-Key: clio_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/FULL_CODEBASE_AUDIT.yaml",
    "files": "**/*.{py,js,ts,tsx}",
    "max_tokens": 200000,
    "parameters": {
      "exclude_paths": ["node_modules/", "*.test.*", "dist/"],
      "priority": "high",
      "parallel_processing": true
    }
  }'
```

## Error Scenarios

### Invalid Workflow File

```bash
curl -X POST "http://localhost:8080/api/v1/workflows/execute" \
  -H "X-API-Key: clio_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/nonexistent.yaml",
    "files": "**/*.py"
  }'
```

**Error Response:**

```json
{
  "error": "workflow_not_found",
  "message": "Workflow file not found: .ai/workflows/nonexistent.yaml",
  "details": {
    "available_workflows": [
      "PY_EDIT_TRIAGE.yaml",
      "JS_LINT_FIX.yaml",
      "FULL_CODEBASE_AUDIT.yaml"
    ]
  },
  "request_id": "req_error_123"
}
```

### Token Limit Exceeded

```bash
curl -X POST "http://localhost:8080/api/v1/workflows/execute" \
  -H "X-API-Key: clio_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/LARGE_WORKFLOW.yaml",
    "files": "**/*",
    "max_tokens": 1000
  }'
```

**Response:**

```json
{
  "execution_id": "exec_token_limit_456",
  "success": false,
  "error": "Token limit exceeded: 1250 > 1000",
  "artifacts": [
    "artifacts/partial_results.json"
  ],
  "tokens_used": 1250,
  "steps_completed": 2,
  "execution_time_seconds": 8.3,
  "workflow_name": "LARGE_WORKFLOW"
}
```

### Authentication Error

```bash
curl -X POST "http://localhost:8080/api/v1/workflows/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/PY_EDIT_TRIAGE.yaml",
    "files": "**/*.py"
  }'
```

**Error Response:**

```json
{
  "error": "unauthorized",
  "message": "Valid API key or JWT token required",
  "details": {
    "supported_auth_methods": ["X-API-Key", "Authorization: Bearer"]
  },
  "request_id": "req_auth_error_789"
}
```

## Language-Specific Examples

### Python Client

```python
import requests
import json

def execute_workflow(api_key, workflow_file, files, **kwargs):
    """Execute CLI Orchestrator workflow"""

    url = "http://localhost:8080/api/v1/workflows/execute"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "workflow_file": workflow_file,
        "files": files,
        **kwargs
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API Error: {response.status_code} - {response.text}")

# Usage
try:
    result = execute_workflow(
        api_key="clio_your_api_key_here",
        workflow_file=".ai/workflows/PY_EDIT_TRIAGE.yaml",
        files="src/**/*.py",
        max_tokens=50000,
        lane="feature/fix-imports"
    )

    print(f"Execution ID: {result['execution_id']}")
    print(f"Success: {result['success']}")
    print(f"Artifacts: {result['artifacts']}")
    print(f"Tokens used: {result['tokens_used']}")

except Exception as e:
    print(f"Error: {e}")
```

### JavaScript/Node.js Client

```javascript
const axios = require('axios');

async function executeWorkflow(apiKey, workflowFile, files, options = {}) {
    const url = 'http://localhost:8080/api/v1/workflows/execute';

    const payload = {
        workflow_file: workflowFile,
        files: files,
        ...options
    };

    try {
        const response = await axios.post(url, payload, {
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            }
        });

        return response.data;
    } catch (error) {
        if (error.response) {
            throw new Error(`API Error: ${error.response.status} - ${error.response.data.message}`);
        }
        throw error;
    }
}

// Usage
(async () => {
    try {
        const result = await executeWorkflow(
            'clio_your_api_key_here',
            '.ai/workflows/JS_LINT_FIX.yaml',
            '**/*.js',
            {
                maxTokens: 25000,
                lane: 'feature/eslint-fixes'
            }
        );

        console.log(`Execution ID: ${result.execution_id}`);
        console.log(`Success: ${result.success}`);
        console.log(`Artifacts: ${result.artifacts}`);
        console.log(`Tokens used: ${result.tokens_used}`);

    } catch (error) {
        console.error(`Error: ${error.message}`);
    }
})();
```

### Bash Script

```bash
#!/bin/bash

# CLI Orchestrator workflow execution script
set -euo pipefail

API_KEY="${CLI_ORCHESTRATOR_API_KEY:-}"
BASE_URL="${CLI_ORCHESTRATOR_URL:-http://localhost:8080/api/v1}"

if [[ -z "$API_KEY" ]]; then
    echo "Error: CLI_ORCHESTRATOR_API_KEY environment variable required"
    exit 1
fi

execute_workflow() {
    local workflow_file="$1"
    local files="$2"
    local max_tokens="${3:-50000}"

    echo "Executing workflow: $workflow_file"
    echo "Files: $files"
    echo "Max tokens: $max_tokens"

    response=$(curl -s -X POST "$BASE_URL/workflows/execute" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"workflow_file\": \"$workflow_file\",
            \"files\": \"$files\",
            \"max_tokens\": $max_tokens
        }")

    echo "Response: $response"

    # Check if execution was successful
    success=$(echo "$response" | jq -r '.success // false')

    if [[ "$success" == "true" ]]; then
        echo "✅ Workflow completed successfully"

        execution_id=$(echo "$response" | jq -r '.execution_id')
        tokens_used=$(echo "$response" | jq -r '.tokens_used')
        artifacts=$(echo "$response" | jq -r '.artifacts[]' | tr '\n' ' ')

        echo "Execution ID: $execution_id"
        echo "Tokens used: $tokens_used"
        echo "Artifacts: $artifacts"

        return 0
    else
        echo "❌ Workflow execution failed"
        error=$(echo "$response" | jq -r '.error // "Unknown error"')
        echo "Error: $error"
        return 1
    fi
}

# Examples
execute_workflow ".ai/workflows/PY_EDIT_TRIAGE.yaml" "src/**/*.py" 50000
execute_workflow ".ai/workflows/JS_LINT_FIX.yaml" "**/*.js" 25000
```

## Monitoring Execution

### Check Workflow Status

```bash
curl -H "X-API-Key: clio_your_api_key_here" \
  "http://localhost:8080/api/v1/workflows/python-triage/status"
```

### List Active Executions

```bash
curl -H "X-API-Key: clio_your_api_key_here" \
  "http://localhost:8080/api/v1/workflows/python-triage/executions"
```

### Download Artifacts

```bash
# List available artifacts
curl -H "X-API-Key: clio_your_api_key_here" \
  "http://localhost:8080/api/v1/artifacts"

# Download specific artifact
curl -H "X-API-Key: clio_your_api_key_here" \
  "http://localhost:8080/api/v1/artifacts/diagnostics.json" \
  -o diagnostics.json
```

## Best Practices

### 1. Token Management

- Start with conservative token limits
- Monitor token usage patterns
- Increase limits based on actual needs
- Use dry runs to estimate token requirements

### 2. Error Handling

- Always check the `success` field in responses
- Implement retry logic for transient failures
- Log execution IDs for debugging
- Handle rate limiting gracefully

### 3. Performance Optimization

- Use specific file patterns to limit scope
- Leverage dry runs for validation
- Monitor execution times
- Use appropriate token limits

### 4. Security

- Store API keys securely
- Use environment variables
- Rotate keys regularly
- Monitor API usage for anomalies

## Troubleshooting

### Common Issues

1. **Workflow Not Found**
   - Verify workflow file exists
   - Check file path spelling
   - Ensure workflow is in `.ai/workflows/`

2. **Permission Denied**
   - Check API key validity
   - Verify user permissions
   - Ensure workflow access rights

3. **Token Limit Exceeded**
   - Increase `max_tokens` parameter
   - Reduce file scope with specific patterns
   - Use dry run to estimate requirements

4. **Execution Timeout**
   - Check workflow complexity
   - Monitor system resources
   - Consider breaking into smaller workflows
