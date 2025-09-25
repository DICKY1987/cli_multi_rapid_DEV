"""
Security Framework for CLI Orchestrator.

Provides comprehensive security management including authentication,
authorization, audit logging, and secure execution contexts.
"""

import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Permission(Enum):
    """CLI Orchestrator permissions."""

    # Workflow permissions
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:write"
    WORKFLOW_EXECUTE = "workflow:execute"
    WORKFLOW_DELETE = "workflow:delete"

    # Adapter permissions
    ADAPTER_USE_DETERMINISTIC = "adapter:use_deterministic"
    ADAPTER_USE_AI = "adapter:use_ai"
    ADAPTER_INSTALL = "adapter:install"
    ADAPTER_CONFIGURE = "adapter:configure"

    # System permissions
    SYSTEM_METRICS_VIEW = "system:metrics_view"
    SYSTEM_HEALTH_VIEW = "system:health_view"
    SYSTEM_CONFIG_VIEW = "system:config_view"
    SYSTEM_CONFIG_EDIT = "system:config_edit"

    # Admin permissions
    ADMIN_USER_MANAGEMENT = "admin:user_management"
    ADMIN_SECURITY_AUDIT = "admin:security_audit"
    ADMIN_SYSTEM_CONTROL = "admin:system_control"

    # API permissions
    API_KEY_CREATE = "api:key_create"  # pragma: allowlist secret
    API_KEY_REVOKE = "api:key_revoke"  # pragma: allowlist secret


class Role(Enum):
    """CLI Orchestrator roles."""

    GUEST = "guest"
    DEVELOPER = "developer"
    OPERATOR = "operator"
    ADMIN = "admin"
    SYSTEM = "system"


@dataclass
class User:
    """User entity for CLI Orchestrator."""

    id: str
    username: str
    email: str
    roles: set[Role] = field(default_factory=set)
    permissions: set[Permission] = field(default_factory=set)
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    api_keys: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityPolicy:
    """Security policy configuration for CLI Orchestrator."""

    jwt_secret: str = "cli-orchestrator-dev-secret"
    jwt_expiry_hours: int = 24
    api_key_expiry_days: int = 365
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    password_min_length: int = 8
    require_api_key_for_execution: bool = True
    allowed_workflow_patterns: list[str] = field(
        default_factory=lambda: ["*.yaml", "*.yml"]
    )
    blocked_adapters: list[str] = field(default_factory=list)
    max_concurrent_workflows: int = 10
    rate_limit_per_minute: int = 60


class SecurityFramework:
    """
    Comprehensive security framework for CLI Orchestrator.

    Provides authentication, authorization, audit logging,
    and secure execution contexts for workflow operations.
    """

    def __init__(
        self,
        policy: Optional[SecurityPolicy] = None,
        storage_dir: Optional[Path] = None,
    ):
        self.policy = policy or SecurityPolicy()
        self.storage_dir = storage_dir or Path("security")
        self.storage_dir.mkdir(exist_ok=True)

        # Core components
        from .audit import AuditLogger
        from .auth import APIKeyManager, JWTManager
        from .rbac import RoleBasedAccessControl

        self.jwt_manager = JWTManager(
            self.policy.jwt_secret, self.policy.jwt_expiry_hours
        )
        self.api_key_manager = APIKeyManager(self.storage_dir / "api_keys.json")
        self.rbac = RoleBasedAccessControl()
        self.audit = AuditLogger(self.storage_dir / "audit.jsonl")

        # Security state
        self._users: dict[str, User] = {}
        self._sessions: dict[str, dict] = {}
        self._rate_limits: dict[str, list[float]] = {}
        self._active_workflows: dict[str, dict] = {}

        # Load persisted data
        self._load_users()
        self._setup_default_permissions()

    def _setup_default_permissions(self) -> None:
        """Setup default role permissions for CLI Orchestrator."""

        # Guest permissions (read-only)
        self.rbac.assign_permissions_to_role(
            Role.GUEST,
            [
                Permission.WORKFLOW_READ,
                Permission.SYSTEM_HEALTH_VIEW,
                Permission.SYSTEM_METRICS_VIEW,
            ],
        )

        # Developer permissions (workflow development)
        self.rbac.assign_permissions_to_role(
            Role.DEVELOPER,
            [
                Permission.WORKFLOW_READ,
                Permission.WORKFLOW_WRITE,
                Permission.WORKFLOW_EXECUTE,
                Permission.ADAPTER_USE_DETERMINISTIC,
                Permission.ADAPTER_USE_AI,
                Permission.SYSTEM_HEALTH_VIEW,
                Permission.SYSTEM_METRICS_VIEW,
                Permission.SYSTEM_CONFIG_VIEW,
            ],
        )

        # Operator permissions (production operations)
        self.rbac.assign_permissions_to_role(
            Role.OPERATOR,
            [
                Permission.WORKFLOW_READ,
                Permission.WORKFLOW_EXECUTE,
                Permission.ADAPTER_USE_DETERMINISTIC,
                Permission.SYSTEM_HEALTH_VIEW,
                Permission.SYSTEM_METRICS_VIEW,
                Permission.SYSTEM_CONFIG_VIEW,
                Permission.API_KEY_CREATE,
            ],
        )

        # Admin permissions (all)
        self.rbac.assign_permissions_to_role(Role.ADMIN, list(Permission))

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: Optional[set[Role]] = None,
    ) -> User:
        """Create a new user with CLI Orchestrator access."""

        if username in self._users:
            raise ValueError(f"User {username} already exists")

        # Validate password
        if len(password) < self.policy.password_min_length:
            raise ValueError(
                f"Password must be at least {self.policy.password_min_length} characters"
            )

        user = User(
            id=secrets.token_urlsafe(16),
            username=username,
            email=email,
            roles=roles or {Role.DEVELOPER},
        )

        # Calculate permissions from roles
        user.permissions = self.rbac.get_permissions_for_roles(user.roles)

        # Store password hash
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), secrets.token_bytes(32), 100000
        )
        user.metadata["password_hash"] = password_hash.hex()

        self._users[username] = user
        self._save_users()

        await self.audit.log_event(
            user_id=user.id,
            action="user_created",
            resource="user",
            resource_id=user.id,
            details={
                "username": username,
                "email": email,
                "roles": [r.value for r in roles or []],
            },
        )

        return user

    async def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return JWT token."""
        user = self._users.get(username)
        if not user or not user.is_active:
            await self.audit.log_event(
                user_id=username,
                action="login_failed",
                resource="auth",
                details={"reason": "user_not_found_or_inactive"},
            )
            return None

        # Check lockout
        if self._is_user_locked_out(user.id):
            await self.audit.log_event(
                user_id=user.id,
                action="login_failed",
                resource="auth",
                details={"reason": "account_locked"},
            )
            return None

        # Verify password
        stored_hash = user.metadata.get("password_hash", "")
        if not self._verify_password(password, stored_hash):
            self._record_failed_login(user.id)
            await self.audit.log_event(
                user_id=user.id,
                action="login_failed",
                resource="auth",
                details={"reason": "invalid_password"},
            )
            return None

        # Clear failed attempts
        self._clear_failed_logins(user.id)

        # Update last login
        user.last_login = time.time()
        self._save_users()

        # Generate JWT token
        token = self.jwt_manager.create_token(user)

        await self.audit.log_event(
            user_id=user.id,
            action="login_success",
            resource="auth",
            details={"username": username},
        )

        return token

    async def create_api_key(self, user_id: str, description: str = "") -> str:
        """Create API key for programmatic access."""
        user = next((u for u in self._users.values() if u.id == user_id), None)
        if not user:
            raise ValueError("User not found")

        if not self.rbac.check_permission(user, Permission.API_KEY_CREATE):
            raise ValueError("User does not have permission to create API keys")

        api_key = self.api_key_manager.create_key(user_id, description)
        user.api_keys.add(api_key)
        self._save_users()

        await self.audit.log_event(
            user_id=user_id,
            action="api_key_created",
            resource="api_key",
            details={"description": description},
        )

        return api_key

    async def verify_api_key(self, api_key: str) -> Optional[User]:
        """Verify API key and return associated user."""
        key_info = self.api_key_manager.verify_key(api_key)
        if not key_info:
            return None

        user = next(
            (u for u in self._users.values() if u.id == key_info["user_id"]), None
        )
        if not user or not user.is_active:
            return None

        return user

    async def check_workflow_permission(
        self, user: User, workflow_file: str, action: str
    ) -> bool:
        """Check if user has permission to perform action on workflow."""

        # Map action to permission
        permission_map = {
            "read": Permission.WORKFLOW_READ,
            "write": Permission.WORKFLOW_WRITE,
            "execute": Permission.WORKFLOW_EXECUTE,
            "delete": Permission.WORKFLOW_DELETE,
        }

        required_permission = permission_map.get(action)
        if not required_permission:
            return False

        if not self.rbac.check_permission(user, required_permission):
            await self.audit.log_event(
                user_id=user.id,
                action="permission_denied",
                resource="workflow",
                resource_id=workflow_file,
                details={"action": action, "permission": required_permission.value},
            )
            return False

        # Check workflow pattern restrictions
        workflow_path = Path(workflow_file)
        allowed = any(
            workflow_path.match(pattern)
            for pattern in self.policy.allowed_workflow_patterns
        )

        if not allowed:
            await self.audit.log_event(
                user_id=user.id,
                action="workflow_pattern_blocked",
                resource="workflow",
                resource_id=workflow_file,
                details={"patterns": self.policy.allowed_workflow_patterns},
            )
            return False

        return True

    async def check_adapter_permission(self, user: User, adapter_name: str) -> bool:
        """Check if user has permission to use specific adapter."""

        # Check if adapter is blocked
        if adapter_name in self.policy.blocked_adapters:
            await self.audit.log_event(
                user_id=user.id,
                action="adapter_blocked",
                resource="adapter",
                resource_id=adapter_name,
            )
            return False

        # Check adapter type permissions (simplified)
        if "ai" in adapter_name.lower():
            required_permission = Permission.ADAPTER_USE_AI
        else:
            required_permission = Permission.ADAPTER_USE_DETERMINISTIC

        if not self.rbac.check_permission(user, required_permission):
            await self.audit.log_event(
                user_id=user.id,
                action="permission_denied",
                resource="adapter",
                resource_id=adapter_name,
                details={"permission": required_permission.value},
            )
            return False

        return True

    async def check_rate_limit(self, user_id: str, action: str) -> bool:
        """Check if user is within rate limits."""
        key = f"{user_id}:{action}"
        current_time = time.time()
        window_start = current_time - 60  # 1 minute window

        # Get current requests in window
        if key not in self._rate_limits:
            self._rate_limits[key] = []

        # Remove old entries
        self._rate_limits[key] = [t for t in self._rate_limits[key] if t > window_start]

        # Check limit
        if len(self._rate_limits[key]) >= self.policy.rate_limit_per_minute:
            await self.audit.log_event(
                user_id=user_id,
                action="rate_limit_exceeded",
                resource="rate_limit",
                details={"action": action, "limit": self.policy.rate_limit_per_minute},
            )
            return False

        # Add current request
        self._rate_limits[key].append(current_time)
        return True

    async def start_workflow_execution(
        self, user_id: str, workflow_id: str, workflow_data: dict
    ) -> bool:
        """Register workflow execution start."""
        # Check concurrent workflow limit
        active_user_workflows = [
            w for w in self._active_workflows.values() if w["user_id"] == user_id
        ]

        if len(active_user_workflows) >= self.policy.max_concurrent_workflows:
            await self.audit.log_event(
                user_id=user_id,
                action="concurrent_workflow_limit_exceeded",
                resource="workflow",
                resource_id=workflow_id,
                details={"limit": self.policy.max_concurrent_workflows},
            )
            return False

        self._active_workflows[workflow_id] = {
            "user_id": user_id,
            "start_time": time.time(),
            "workflow_data": workflow_data,
        }

        await self.audit.log_event(
            user_id=user_id,
            action="workflow_execution_started",
            resource="workflow",
            resource_id=workflow_id,
        )

        return True

    async def end_workflow_execution(self, workflow_id: str, success: bool) -> None:
        """Register workflow execution completion."""
        if workflow_id not in self._active_workflows:
            return

        workflow_info = self._active_workflows.pop(workflow_id)
        duration = time.time() - workflow_info["start_time"]

        await self.audit.log_event(
            user_id=workflow_info["user_id"],
            action="workflow_execution_completed",
            resource="workflow",
            resource_id=workflow_id,
            details={"success": success, "duration_seconds": duration},
        )

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash."""
        try:
            # This is a simplified implementation
            # In production, use proper password hashing like bcrypt
            test_hash = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), secrets.token_bytes(32), 100000
            )
            return test_hash.hex() == stored_hash
        except:
            return False

    def _is_user_locked_out(self, user_id: str) -> bool:
        """Check if user is currently locked out."""
        # Simplified lockout check
        return False

    def _record_failed_login(self, user_id: str) -> None:
        """Record failed login attempt."""
        # Implementation would track failed attempts
        pass

    def _clear_failed_logins(self, user_id: str) -> None:
        """Clear failed login attempts for user."""
        # Implementation would clear failed attempts
        pass

    def _load_users(self) -> None:
        """Load users from storage."""
        users_file = self.storage_dir / "users.json"
        if not users_file.exists():
            return

        try:
            with open(users_file) as f:
                users_data = json.load(f)

            for username, user_data in users_data.items():
                user = User(**user_data)
                # Convert role strings to enum
                user.roles = {Role(role) for role in user_data.get("roles", [])}
                # Convert permission strings to enum
                user.permissions = {
                    Permission(perm) for perm in user_data.get("permissions", [])
                }
                self._users[username] = user

        except Exception as e:
            logger.error(f"Failed to load users: {e}")

    def _save_users(self) -> None:
        """Save users to storage."""
        users_file = self.storage_dir / "users.json"

        try:
            users_data = {}
            for username, user in self._users.items():
                user_dict = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "roles": [role.value for role in user.roles],
                    "permissions": [perm.value for perm in user.permissions],
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                    "last_login": user.last_login,
                    "api_keys": list(user.api_keys),
                    "metadata": user.metadata,
                }
                users_data[username] = user_dict

            with open(users_file, "w") as f:
                json.dump(users_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save users: {e}")

    def get_security_summary(self) -> dict[str, Any]:
        """Get security framework status summary."""
        return {
            "total_users": len(self._users),
            "active_users": len([u for u in self._users.values() if u.is_active]),
            "active_workflows": len(self._active_workflows),
            "total_api_keys": sum(len(u.api_keys) for u in self._users.values()),
            "policy": {
                "require_api_key_for_execution": self.policy.require_api_key_for_execution,
                "max_concurrent_workflows": self.policy.max_concurrent_workflows,
                "rate_limit_per_minute": self.policy.rate_limit_per_minute,
            },
        }
