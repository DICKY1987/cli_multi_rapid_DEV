# Branch-Scoped JWT Tokens (MOD-004)

Enhanced JWT authentication system with task and branch-scoped permissions for secure tool execution and API access.

## Quick Reference

- **Enhanced JWT**: Branch and task-scoped tokens with tool restrictions
- **Security Gateway**: Token distribution and validation system
- **Tool Wrappers**: Auto-generated validation scripts for tool execution
- **API Keys**: Programmatic access with API key management

### Core API

```python
# Create scoped tokens
jwt_manager = JWTManager(secret_key)
token = jwt_manager.create_scoped_token(
    task_id="task-123",
    branch="feature/fix-auth",
    tool="aider",
    permissions=["tool:aider", "read:state", "write:artifacts"]
)

# Security gateway for token distribution
gateway = SecurityGateway(jwt_manager)
tool_token = gateway.distribute_token_to_tool(
    task_id="task-123",
    tool="aider",
    permissions=["tool:aider"]
)

# Validate tool access
is_valid = gateway.validate_tool_access(
    token=tool_token,
    requested_task_id="task-123",
    requested_tool="aider",
    required_permissions=["tool:aider"]
)
```

## Token Types and Scopes

### Token Scope Structure
```python
@dataclass
class TokenScope:
    task_id: Optional[str] = None       # Restrict to specific task
    branch: Optional[str] = None        # Restrict to specific branch
    tool: Optional[str] = None          # Restrict to specific tool
    permissions: List[str] = []         # Required permissions
    expires_at: Optional[float] = None  # Expiration timestamp
    metadata: Dict[str, Any] = {}       # Additional context
```

### Scoped Token Claims
```json
{
  "iss": "cli-orchestrator",
  "iat": 1695234567,
  "exp": 1695238167,
  "sub": "system",
  "task_id": "task-123",
  "branch": "feature/auth-tokens",
  "tool": "aider",
  "permissions": ["tool:aider", "read:state", "write:artifacts"],
  "scope": "task_execution",
  "version": "2.0",
  "token_type": "tool_access"
}
```

## Token Creation Methods

### 1. Scoped Tokens (Full Control)
```python
token = jwt_manager.create_scoped_token(
    task_id="task-123",
    branch="feature/auth",
    tool="aider",
    permissions=["tool:aider", "read:state"],
    expiry_minutes=60,
    user_id="system",
    custom_metadata="value"
)
```

### 2. Tool-Specific Tokens (Minimal Permissions)
```python
token = jwt_manager.create_tool_token(
    task_id="task-123",
    tool="aider",
    permissions=["tool:aider"],
    branch="feature/auth",
    expiry_minutes=30  # Short-lived for security
)
```

### 3. Phase Tokens (Multi-Tool Access)
```python
token = jwt_manager.create_phase_token(
    task_id="task-123",
    phase="code_analysis",
    tools=["aider", "pytest", "ruff"],
    branch="feature/auth",
    expiry_minutes=120
)
```

### 4. Legacy Tokens (Backward Compatibility)
```python
# Legacy user tokens still supported
token = jwt_manager.create_token(user)
```

## Token Validation and Security

### Enhanced Validation
```python
# Validate with specific requirements
payload = jwt_manager.verify_scoped_token(
    token=token,
    required_task_id="task-123",
    required_tool="aider",
    required_permissions=["tool:aider", "read:state"]
)

# Validate against TokenScope object
scope = TokenScope(
    task_id="task-123",
    tool="aider",
    permissions=["tool:aider"]
)
is_valid = jwt_manager.validate_token_scope(token, scope)
```

### Token Information Extraction
```python
# Extract claims into TokenScope object
scope = jwt_manager.extract_token_claims(token)
print(f"Task: {scope.task_id}, Tool: {scope.tool}")

# Get token info for debugging
info = jwt_manager.get_token_info(token)
print(f"Expires: {info['expires_at']}")

# Check expiration without full validation
is_expired = jwt_manager.is_token_expired(token)
```

## Security Gateway Operations

### Token Distribution
```python
gateway = SecurityGateway(jwt_manager)

# Distribute token to tool via environment
token = gateway.distribute_token_to_tool(
    task_id="task-123",
    tool="aider",
    permissions=["tool:aider", "read:state"],
    branch="feature/auth"
)

# Token is tracked in active tokens registry
print(f"Active tokens: {gateway.get_active_tokens_info()}")
```

### Access Validation
```python
# Validate tool access with comprehensive checks
is_authorized = gateway.validate_tool_access(
    token=token,
    requested_task_id="task-123",
    requested_tool="aider",
    required_permissions=["tool:aider"]
)

# Security events are automatically emitted for failures
```

### Token Management
```python
# Revoke all tokens for a task
revoked_count = gateway.revoke_task_tokens("task-123")

# Clean up expired tokens
expired_count = gateway.cleanup_expired_tokens()

# Get active token statistics
stats = gateway.get_active_tokens_info()
print(f"Active: {stats['active_tokens']}, Expired: {stats['expired_tokens']}")
```

## Tool Wrapper Scripts

### Auto-Generated Wrappers
```python
# Create secure wrapper script for tool
wrapper_script = gateway.create_wrapper_script("aider", token)

# Wrapper validates token before tool execution
# Environment variables: IPT_TOKEN, IPT_TASK_ID
# Exits with error if validation fails
```

### Wrapper Script Example
```python
#!/usr/bin/env python3
# Auto-generated token validation wrapper for aider

import os
import sys
from cli_multi_rapid.security.auth import SecurityGateway, JWTManager

# Initialize security components
jwt_manager = JWTManager(os.environ.get("JWT_SECRET"))
gateway = SecurityGateway(jwt_manager)

# Validate token before tool execution
token = os.environ.get("IPT_TOKEN")
task_id = os.environ.get("IPT_TASK_ID")

if not gateway.validate_tool_access(
    token=token,
    requested_task_id=task_id,
    requested_tool="aider",
    required_permissions=["tool:aider"]
):
    print("ERROR: Token validation failed", file=sys.stderr)
    sys.exit(1)

# Execute actual tool
import subprocess
result = subprocess.run(["aider"] + sys.argv[1:])
sys.exit(result.returncode)
```

## API Key Management

### API Key Creation
```python
api_key_manager = APIKeyManager(Path("config/api_keys.json"))

# Create API key for user
api_key = api_key_manager.create_key(
    user_id="user123",
    description="CI/CD automation key",
    expiry_days=90
)
```

### API Key Validation
```python
# Verify API key
key_data = api_key_manager.verify_key(api_key)
if key_data:
    print(f"Valid key for user: {key_data['user_id']}")

# List user's keys
user_keys = api_key_manager.list_keys_for_user("user123")

# Revoke API key
api_key_manager.revoke_key(api_key)
```

### API Key Statistics
```python
stats = api_key_manager.get_key_stats()
print(f"Total: {stats['total_keys']}, Active: {stats['active_keys']}")

# Cleanup expired keys
expired_count = api_key_manager.cleanup_expired_keys()
```

## Production Security Features

### RSA Key Generation
```python
# Generate RSA key pair for production JWT signing
gateway.generate_rsa_keys()

# Creates:
# - config/jwt_private.pem (600 permissions)
# - config/jwt_public.pem (644 permissions)
```

### Security Event Monitoring
```python
# Security events are automatically emitted to event bus
# Topics: security.events
# Event types:
# - token_validation_failed
# - token_not_found
# - tokens_revoked
```

## Integration Examples

### Workflow Integration
```yaml
# In workflow YAML
steps:
  - id: "secure_editing"
    name: "AI Code Editing with Scoped Token"
    actor: ai_editor
    with:
      tool: aider
      security:
        token_scope:
          task_id: "{{task_id}}"
          branch: "{{branch}}"
          permissions: ["tool:aider", "read:state", "write:artifacts"]
        token_expiry: 30
```

### Adapter Integration
```python
# In adapter implementation
class SecureAdapter(BaseAdapter):
    def execute(self, params, context):
        # Get scoped token for this execution
        token = context.security_gateway.distribute_token_to_tool(
            task_id=context.task_id,
            tool=self.tool_name,
            permissions=self.required_permissions,
            branch=context.branch
        )

        # Set environment for tool execution
        env = os.environ.copy()
        env['IPT_TOKEN'] = token
        env['IPT_TASK_ID'] = context.task_id

        # Execute tool with token validation
        return self._execute_with_token(params, env)
```

### Event Bus Integration
```python
# Security events automatically published
publisher = EventBusPublisher()
publisher.publish_event_sync(
    event_type="token_validation_failed",
    topic="security.events",
    payload={
        "task_id": "task-123",
        "tool": "aider",
        "reason": "invalid_token",
        "severity": "warning"
    }
)
```

## Permission System

### Standard Permissions
- **`tool:<tool_name>`** - Access to specific tool
- **`read:state`** - Read task state and context
- **`write:artifacts`** - Write execution artifacts
- **`read:config`** - Read configuration files
- **`write:config`** - Modify configuration
- **`admin:tasks`** - Administrative task operations

### Permission Validation
```python
# Check if token has required permissions
required = ["tool:aider", "write:artifacts"]
token_perms = set(payload.get("permissions", []))
missing = set(required) - token_perms

if missing:
    raise PermissionError(f"Missing permissions: {missing}")
```

## Error Handling and Debugging

### Common Token Errors
```python
# Token expired
jwt.ExpiredSignatureError: "Token verification failed: expired"

# Invalid token signature
jwt.InvalidTokenError: "Token verification failed: invalid signature"

# Task ID mismatch
"Token task_id mismatch: task-456 != task-123"

# Tool access denied
"Token tool access denied: pytest not in aider/[aider, ruff]"

# Missing permissions
"Token missing permissions: {'write:config'}"
```

### Debugging Tools
```python
# Decode token without verification (debugging only)
payload = jwt_manager.decode_token_without_verification(token)
print(json.dumps(payload, indent=2))

# Get detailed token information
info = jwt_manager.get_token_info(token)
print(f"Tool: {info['tool']}, Expires: {info['expires_at']}")

# Check active tokens
stats = gateway.get_active_tokens_info()
print(f"Tokens by task: {stats['tokens_by_task']}")
```

## Security Best Practices

### Token Lifecycle
1. **Short Expiry**: Use short expiration times (15-60 minutes)
2. **Minimal Permissions**: Grant only required permissions
3. **Task Scoping**: Always scope tokens to specific tasks
4. **Automatic Cleanup**: Regularly clean up expired tokens
5. **Event Monitoring**: Monitor security events for anomalies

### Production Deployment
1. **RSA Keys**: Use RSA keys instead of HMAC in production
2. **Secure Storage**: Store JWT secrets in secure key management
3. **Token Blacklist**: Implement Redis-based token blacklist
4. **Rate Limiting**: Add rate limiting for token creation
5. **Audit Logging**: Log all token operations

### Environment Security
```bash
# Required environment variables
export JWT_SECRET="your-256-bit-secret"  # pragma: allowlist secret
export IPT_TOKEN="scoped-jwt-token"  # pragma: allowlist secret
export IPT_TASK_ID="current-task-id"  # pragma: allowlist secret

# Optional production settings
export JWT_ALGORITHM="RS256"  # Use RSA for production
export JWT_PRIVATE_KEY_PATH="/secure/jwt_private.pem"
export JWT_PUBLIC_KEY_PATH="/secure/jwt_public.pem"
```

## Acceptance Criteria ✅

- ✅ JWT tokens include `task_id` and `branch` in claims
- ✅ Token validation checks task and tool scope restrictions
- ✅ SecurityGateway distributes scoped tokens to tools
- ✅ Tool wrapper scripts validate tokens before execution
- ✅ Legacy JWT tokens remain backward compatible
- ✅ API key management for programmatic access
- ✅ Security events emitted to event bus for monitoring
- ✅ RSA key generation for production JWT signing

For detailed implementation, see `src/cli_multi_rapid/security/auth.py`.
