"""
Security tests for CLI Orchestrator Security Framework.

Tests authentication, authorization, audit logging,
and security policy enforcement.
"""

import pytest

from src.cli_multi_rapid.security.framework import (
    Permission,
    Role,
    SecurityFramework,
    SecurityPolicy,
)


@pytest.mark.security
class TestSecurityFramework:
    """Test SecurityFramework core functionality."""

    @pytest_asyncio.fixture
    async def security_framework(self, temp_dir, test_security_policy):
        """Create SecurityFramework for testing."""
        framework = SecurityFramework(test_security_policy, temp_dir / "security")
        return framework

    async def test_create_user_success(self, security_framework):
        """Test successful user creation."""
        user = await security_framework.create_user(
            username="newuser",
            email="newuser@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert Role.DEVELOPER in user.roles
        assert user.is_active is True
        assert user.id is not None

    async def test_create_duplicate_user(self, security_framework):
        """Test creating duplicate user fails."""
        await security_framework.create_user(
            username="testuser", email="test@example.com", password="password123"
        )

        with pytest.raises(ValueError, match="already exists"):
            await security_framework.create_user(
                username="testuser", email="another@example.com", password="password123"
            )

    async def test_create_user_weak_password(self, security_framework):
        """Test creating user with weak password fails."""
        with pytest.raises(ValueError, match="Password must be at least"):
            await security_framework.create_user(
                username="weakuser",
                email="weak@example.com",
                password="123",  # Too short
                roles={Role.DEVELOPER},
            )

    async def test_authenticate_user_success(self, security_framework):
        """Test successful user authentication."""
        # Create user first
        await security_framework.create_user(
            username="authuser",
            email="auth@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        token = await security_framework.authenticate_user("authuser", "password123")

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_authenticate_user_invalid_password(self, security_framework):
        """Test authentication with invalid password."""
        await security_framework.create_user(
            username="authuser",
            email="auth@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        token = await security_framework.authenticate_user("authuser", "wrongpassword")

        assert token is None

    async def test_authenticate_user_nonexistent(self, security_framework):
        """Test authentication with nonexistent user."""
        token = await security_framework.authenticate_user("nonexistent", "password")

        assert token is None

    async def test_create_api_key_success(self, security_framework):
        """Test successful API key creation."""
        user = await security_framework.create_user(
            username="apiuser",
            email="api@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        api_key = await security_framework.create_api_key(
            user_id=user.id, description="Test API key"
        )

        assert api_key is not None
        assert api_key.startswith("clio_")
        assert api_key in user.api_keys

    async def test_verify_api_key_success(self, security_framework):
        """Test successful API key verification."""
        user = await security_framework.create_user(
            username="apiuser",
            email="api@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        api_key = await security_framework.create_api_key(user.id, "Test key")

        verified_user = await security_framework.verify_api_key(api_key)

        assert verified_user is not None
        assert verified_user.id == user.id
        assert verified_user.username == user.username

    async def test_verify_api_key_invalid(self, security_framework):
        """Test API key verification with invalid key."""
        verified_user = await security_framework.verify_api_key("invalid_key")

        assert verified_user is None

    async def test_check_workflow_permission_success(self, security_framework):
        """Test workflow permission check success."""
        user = await security_framework.create_user(
            username="workflowuser",
            email="workflow@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        has_permission = await security_framework.check_workflow_permission(
            user=user, workflow_file="test_workflow.yaml", action="execute"
        )

        assert has_permission is True

    async def test_check_workflow_permission_denied(self, security_framework):
        """Test workflow permission denied."""
        user = await security_framework.create_user(
            username="guestuser",
            email="guest@example.com",
            password="password123",
            roles={Role.GUEST},  # Guest cannot execute workflows
        )

        has_permission = await security_framework.check_workflow_permission(
            user=user, workflow_file="test_workflow.yaml", action="execute"
        )

        assert has_permission is False

    async def test_check_workflow_permission_blocked_pattern(self, security_framework):
        """Test workflow permission blocked by pattern."""
        # Update policy to block certain patterns
        security_framework.policy.allowed_workflow_patterns = ["allowed_*.yaml"]

        user = await security_framework.create_user(
            username="patternuser",
            email="pattern@example.com",
            password="password123",
            roles={Role.ADMIN},  # Even admin blocked by pattern
        )

        has_permission = await security_framework.check_workflow_permission(
            user=user, workflow_file="blocked_workflow.yaml", action="execute"
        )

        assert has_permission is False

    async def test_check_adapter_permission_success(self, security_framework):
        """Test adapter permission check success."""
        user = await security_framework.create_user(
            username="adapteruser",
            email="adapter@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        has_permission = await security_framework.check_adapter_permission(
            user=user, adapter_name="deterministic_adapter"
        )

        assert has_permission is True

    async def test_check_adapter_permission_ai_denied(self, security_framework):
        """Test AI adapter permission denied for guest."""
        user = await security_framework.create_user(
            username="guestuser",
            email="guest@example.com",
            password="password123",
            roles={Role.GUEST},  # Guest cannot use AI adapters
        )

        has_permission = await security_framework.check_adapter_permission(
            user=user, adapter_name="ai_adapter"
        )

        assert has_permission is False

    async def test_check_adapter_permission_blocked(self, security_framework):
        """Test adapter permission blocked by policy."""
        security_framework.policy.blocked_adapters = ["blocked_adapter"]

        user = await security_framework.create_user(
            username="blockeduser",
            email="blocked@example.com",
            password="password123",
            roles={Role.ADMIN},  # Even admin blocked
        )

        has_permission = await security_framework.check_adapter_permission(
            user=user, adapter_name="blocked_adapter"
        )

        assert has_permission is False

    async def test_rate_limiting(self, security_framework):
        """Test rate limiting functionality."""
        user = await security_framework.create_user(
            username="rateuser",
            email="rate@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        # First request should pass
        allowed = await security_framework.check_rate_limit(user.id, "test_action")
        assert allowed is True

        # Simulate many requests to hit limit
        for _ in range(security_framework.policy.rate_limit_per_minute):
            await security_framework.check_rate_limit(user.id, "test_action")

        # Next request should be rate limited
        rate_limited = await security_framework.check_rate_limit(user.id, "test_action")
        assert rate_limited is False

    async def test_workflow_execution_tracking(self, security_framework):
        """Test workflow execution tracking."""
        user = await security_framework.create_user(
            username="execuser",
            email="exec@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        workflow_id = "test_workflow_123"
        workflow_data = {"name": "Test Workflow"}

        # Start workflow execution
        started = await security_framework.start_workflow_execution(
            user_id=user.id, workflow_id=workflow_id, workflow_data=workflow_data
        )

        assert started is True

        # End workflow execution
        await security_framework.end_workflow_execution(workflow_id, success=True)

        # Workflow should no longer be active
        assert workflow_id not in security_framework._active_workflows

    async def test_concurrent_workflow_limit(self, security_framework):
        """Test concurrent workflow execution limit."""
        user = await security_framework.create_user(
            username="concurrentuser",
            email="concurrent@example.com",
            password="password123",
            roles={Role.DEVELOPER},
        )

        # Start workflows up to limit
        workflow_ids = []
        for i in range(security_framework.policy.max_concurrent_workflows):
            workflow_id = f"workflow_{i}"
            started = await security_framework.start_workflow_execution(
                user_id=user.id,
                workflow_id=workflow_id,
                workflow_data={"name": f"Workflow {i}"},
            )
            assert started is True
            workflow_ids.append(workflow_id)

        # Next workflow should be rejected
        exceeded = await security_framework.start_workflow_execution(
            user_id=user.id,
            workflow_id="workflow_overflow",
            workflow_data={"name": "Overflow Workflow"},
        )

        assert exceeded is False

        # Clean up
        for workflow_id in workflow_ids:
            await security_framework.end_workflow_execution(workflow_id, success=True)

    def test_security_summary(self, security_framework):
        """Test security framework summary."""
        summary = security_framework.get_security_summary()

        assert isinstance(summary, dict)
        assert "total_users" in summary
        assert "active_users" in summary
        assert "active_workflows" in summary
        assert "total_api_keys" in summary
        assert "policy" in summary

        assert isinstance(summary["total_users"], int)
        assert isinstance(summary["active_users"], int)
        assert isinstance(summary["active_workflows"], int)
        assert isinstance(summary["total_api_keys"], int)
        assert isinstance(summary["policy"], dict)


@pytest.mark.security
class TestSecurityPolicy:
    """Test SecurityPolicy configuration."""

    def test_security_policy_defaults(self):
        """Test SecurityPolicy default values."""
        policy = SecurityPolicy()

        assert policy.jwt_secret == "cli-orchestrator-dev-secret"
        assert policy.jwt_expiry_hours == 24
        assert policy.api_key_expiry_days == 365
        assert policy.max_login_attempts == 5
        assert policy.lockout_duration_minutes == 15
        assert policy.password_min_length == 8
        assert policy.require_api_key_for_execution is True
        assert policy.allowed_workflow_patterns == ["*.yaml", "*.yml"]
        assert policy.blocked_adapters == []
        assert policy.max_concurrent_workflows == 10
        assert policy.rate_limit_per_minute == 60

    def test_security_policy_custom_values(self):
        """Test SecurityPolicy with custom values."""
        policy = SecurityPolicy(
            jwt_secret="custom-secret",
            jwt_expiry_hours=12,
            max_login_attempts=3,
            password_min_length=12,
            require_api_key_for_execution=False,
            allowed_workflow_patterns=["secure_*.yaml"],
            blocked_adapters=["risky_adapter"],
            max_concurrent_workflows=5,
            rate_limit_per_minute=30,
        )

        assert policy.jwt_secret == "custom-secret"
        assert policy.jwt_expiry_hours == 12
        assert policy.max_login_attempts == 3
        assert policy.password_min_length == 12
        assert policy.require_api_key_for_execution is False
        assert policy.allowed_workflow_patterns == ["secure_*.yaml"]
        assert policy.blocked_adapters == ["risky_adapter"]
        assert policy.max_concurrent_workflows == 5
        assert policy.rate_limit_per_minute == 30


@pytest.mark.security
class TestRolePermissionSystem:
    """Test role and permission system."""

    def test_role_enum_values(self):
        """Test Role enum has expected values."""
        assert Role.GUEST.value == "guest"
        assert Role.DEVELOPER.value == "developer"
        assert Role.OPERATOR.value == "operator"
        assert Role.ADMIN.value == "admin"
        assert Role.SYSTEM.value == "system"

    def test_permission_enum_values(self):
        """Test Permission enum has expected values."""
        workflow_permissions = [
            p for p in Permission if p.value.startswith("workflow:")
        ]
        adapter_permissions = [p for p in Permission if p.value.startswith("adapter:")]
        system_permissions = [p for p in Permission if p.value.startswith("system:")]
        admin_permissions = [p for p in Permission if p.value.startswith("admin:")]

        assert len(workflow_permissions) >= 4  # read, write, execute, delete
        assert len(adapter_permissions) >= 2  # use_deterministic, use_ai
        assert len(system_permissions) >= 3  # metrics, health, config views
        assert len(admin_permissions) >= 2  # user management, security audit

    def test_user_permission_calculation(self, test_security_framework):
        """Test user effective permissions calculation."""
        framework = test_security_framework
        rbac = framework.rbac

        # Test developer role permissions
        developer_permissions = rbac.get_permissions_for_roles({Role.DEVELOPER})

        assert Permission.WORKFLOW_READ in developer_permissions
        assert Permission.WORKFLOW_WRITE in developer_permissions
        assert Permission.WORKFLOW_EXECUTE in developer_permissions
        assert Permission.ADAPTER_USE_DETERMINISTIC in developer_permissions
        assert Permission.ADAPTER_USE_AI in developer_permissions

    def test_guest_role_limitations(self, test_security_framework):
        """Test guest role has limited permissions."""
        framework = test_security_framework
        rbac = framework.rbac

        guest_permissions = rbac.get_permissions_for_roles({Role.GUEST})

        assert Permission.WORKFLOW_READ in guest_permissions
        assert Permission.WORKFLOW_EXECUTE not in guest_permissions
        assert Permission.WORKFLOW_WRITE not in guest_permissions
        assert Permission.ADAPTER_USE_AI not in guest_permissions

    def test_admin_role_has_all_permissions(self, test_security_framework):
        """Test admin role has all permissions."""
        framework = test_security_framework
        rbac = framework.rbac

        admin_permissions = rbac.get_permissions_for_roles({Role.ADMIN})

        # Admin should have all permissions
        all_permissions = set(Permission)
        assert admin_permissions == all_permissions
