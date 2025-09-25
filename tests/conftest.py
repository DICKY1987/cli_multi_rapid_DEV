"""
Master test configuration for CLI Orchestrator.

Provides comprehensive testing infrastructure including:
- Fixture management for services and components
- Mock adapters and workflow runners
- Test data factories
- Performance monitoring
- Contract validation utilities
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
import yaml

from src.cli_multi_rapid.adapters.base_adapter import (
    AdapterResult,
    AdapterType,
    BaseAdapter,
)
from src.cli_multi_rapid.enterprise.base_service import (
    BaseEnterpriseService,
    ServiceMetadata,
)
from src.cli_multi_rapid.enterprise.config import ServiceConfig
from src.cli_multi_rapid.security.framework import (
    Role,
    SecurityFramework,
    SecurityPolicy,
)

# Import CLI Orchestrator components
from src.cli_multi_rapid.workflow_runner import WorkflowResult, WorkflowRunner

# Test Categories
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.timeout(30),  # Default timeout for all tests
]


class TestCategories:
    """Test category markers for pytest."""

    UNIT = pytest.mark.unit
    INTEGRATION = pytest.mark.integration
    E2E = pytest.mark.e2e
    CONTRACT = pytest.mark.contract
    PERFORMANCE = pytest.mark.performance
    SECURITY = pytest.mark.security
    SLOW = pytest.mark.slow


# Core Fixtures


@pytest_asyncio.fixture(scope="session")
async def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config(temp_dir):
    """Test service configuration."""
    return ServiceConfig(
        service_name="test-cli-orchestrator",
        environment="test",
        host="localhost",
        port=8080,
        workflow_schema_dir=str(temp_dir / "schemas"),
        artifacts_dir=str(temp_dir / "artifacts"),
        logs_dir=str(temp_dir / "logs"),
        jwt_secret="test-secret-key",
        log_level="DEBUG",
    )


@pytest.fixture
def test_security_policy():
    """Test security policy."""
    return SecurityPolicy(
        jwt_secret="test-secret-key-for-testing-only",
        jwt_expiry_hours=1,
        max_login_attempts=3,
        lockout_duration_minutes=5,
        password_min_length=6,
        require_api_key_for_execution=False,
        allowed_workflow_patterns=["*.yaml", "*.yml", "test_*.yaml"],
        rate_limit_per_minute=100,
    )


@pytest_asyncio.fixture
async def test_security_framework(temp_dir, test_security_policy):
    """Test security framework with test users."""
    framework = SecurityFramework(test_security_policy, temp_dir / "security")

    # Create test users
    await framework.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        roles={Role.DEVELOPER},
    )

    await framework.create_user(
        username="testadmin",
        email="admin@example.com",
        password="adminpass123",
        roles={Role.ADMIN},
    )

    yield framework


# Mock Adapters


class MockDeterministicAdapter(BaseAdapter):
    """Mock deterministic adapter for testing."""

    def __init__(self):
        super().__init__(
            name="mock_deterministic",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Mock deterministic adapter for testing",
        )

    def execute(self, step, context=None, files=None):
        return AdapterResult(
            success=True,
            tokens_used=0,
            artifacts=["test_artifact.json"],
            output="Mock deterministic execution completed",
        )

    def validate_step(self, step):
        return step.get("actor") == "mock_deterministic"

    def estimate_cost(self, step):
        return 0


class MockAIAdapter(BaseAdapter):
    """Mock AI adapter for testing."""

    def __init__(self):
        super().__init__(
            name="mock_ai",
            adapter_type=AdapterType.AI,
            description="Mock AI adapter for testing",
        )

    def execute(self, step, context=None, files=None):
        return AdapterResult(
            success=True,
            tokens_used=100,
            artifacts=["ai_output.json"],
            output="Mock AI execution completed",
        )

    def validate_step(self, step):
        return step.get("actor") == "mock_ai"

    def estimate_cost(self, step):
        return 100


@pytest.fixture
def mock_adapters():
    """Mock adapters for testing."""
    return {
        "mock_deterministic": MockDeterministicAdapter(),
        "mock_ai": MockAIAdapter(),
    }


# Service Fixtures


class MockService(BaseEnterpriseService):
    """Mock service for testing enterprise capabilities."""

    def __init__(self, config: ServiceConfig):
        metadata = ServiceMetadata(
            name="test-service",
            version="1.0.0",
            description="Test service for unit tests",
            dependencies=[],
            health_check_interval=10,
            metrics_enabled=True,
            api_enabled=True,
        )

        super().__init__(metadata, config)
        self.mock_impl = AsyncMock()

    async def service_logic(self):
        """Mock service logic."""
        await self.mock_impl.start()

    async def cleanup(self):
        """Mock cleanup."""
        await self.mock_impl.stop()


@pytest_asyncio.fixture
async def test_service(test_config):
    """Test service instance."""
    service = MockService(test_config)
    yield service
    await service.cleanup()


# Workflow Fixtures


@pytest.fixture
def sample_workflow():
    """Sample workflow definition for testing."""
    return {
        "name": "Test Workflow",
        "version": "1.0.0",
        "description": "Sample workflow for testing",
        "inputs": {"files": ["**/*.py"], "lane": "test"},
        "policy": {"max_tokens": 1000, "prefer_deterministic": True},
        "steps": [
            {
                "id": "1.001",
                "name": "Mock Deterministic Step",
                "actor": "mock_deterministic",
                "with": {"test_param": "test_value"},
                "emits": ["test_output.json"],
            },
            {
                "id": "1.002",
                "name": "Mock AI Step",
                "actor": "mock_ai",
                "with": {"ai_param": "ai_value"},
                "emits": ["ai_output.json"],
                "when": "success(1.001)",
            },
        ],
    }


@pytest.fixture
def workflow_file(temp_dir, sample_workflow):
    """Create sample workflow file."""
    workflow_file = temp_dir / "test_workflow.yaml"
    with open(workflow_file, "w") as f:
        yaml.dump(sample_workflow, f)
    return workflow_file


@pytest.fixture
def workflow_schema(temp_dir):
    """Create workflow schema file."""
    schema_dir = temp_dir / "schemas"
    schema_dir.mkdir(exist_ok=True)

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "version": {"type": "string"},
            "description": {"type": "string"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "actor": {"type": "string"},
                    },
                    "required": ["id", "name", "actor"],
                },
            },
        },
        "required": ["name", "steps"],
    }

    schema_file = schema_dir / "workflow.schema.json"
    with open(schema_file, "w") as f:
        json.dump(schema, f, indent=2)

    return schema_file


@pytest.fixture
def mock_workflow_runner(mock_adapters):
    """Mock workflow runner with test adapters."""
    runner = WorkflowRunner()
    # Mock the router to return our test adapters
    runner.router = MagicMock()
    runner.router.route_step.return_value = MagicMock(
        adapter_name="mock_deterministic",
        reasoning="Mock routing decision",
        estimated_tokens=0,
    )
    runner.router.registry.get_adapter.return_value = mock_adapters[
        "mock_deterministic"
    ]

    return runner


# Test Data Factories


class TestDataFactory:
    """Factory for generating test data."""

    @staticmethod
    def create_workflow_data(**overrides) -> Dict[str, Any]:
        """Create test workflow data."""
        base_workflow = {
            "name": "Test Workflow",
            "version": "1.0.0",
            "description": "Test workflow for unit testing",
            "inputs": {"files": ["**/*.py"], "lane": "test"},
            "steps": [
                {
                    "id": "step_001",
                    "name": "Test Step",
                    "actor": "mock_deterministic",
                    "with": {"param": "value"},
                    "emits": ["output.json"],
                }
            ],
        }

        base_workflow.update(overrides)
        return base_workflow

    @staticmethod
    def create_adapter_result(**overrides) -> AdapterResult:
        """Create test adapter result."""
        defaults = {
            "success": True,
            "tokens_used": 50,
            "artifacts": ["test_artifact.json"],
            "output": "Test execution completed",
            "error": None,
            "metadata": {},
        }

        defaults.update(overrides)
        return AdapterResult(**defaults)

    @staticmethod
    def create_workflow_result(**overrides) -> WorkflowResult:
        """Create test workflow result."""
        defaults = {
            "success": True,
            "error": None,
            "artifacts": ["output.json"],
            "tokens_used": 100,
            "steps_completed": 2,
        }

        defaults.update(overrides)
        return WorkflowResult(**defaults)

    @staticmethod
    def create_user_data(**overrides) -> Dict[str, Any]:
        """Create test user data."""
        defaults = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123",
            "roles": [Role.DEVELOPER.value],
        }

        defaults.update(overrides)
        return defaults


@pytest.fixture
def test_data_factory():
    """Test data factory instance."""
    return TestDataFactory()


# Test Utilities


class TestUtils:
    """Utilities for testing."""

    @staticmethod
    async def wait_for_condition(
        condition_func, timeout: float = 5.0, poll_interval: float = 0.1
    ):
        """Wait for a condition to become true."""
        start_time = asyncio.get_event_loop().time()

        while True:
            if (
                await condition_func()
                if asyncio.iscoroutinefunction(condition_func)
                else condition_func()
            ):
                return True

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"Condition not met within {timeout} seconds")

            await asyncio.sleep(poll_interval)

    @staticmethod
    def assert_valid_workflow_result(result: WorkflowResult):
        """Assert that workflow result is valid."""
        assert isinstance(result, WorkflowResult)
        assert isinstance(result.success, bool)
        assert isinstance(result.tokens_used, int)
        assert isinstance(result.steps_completed, int)
        assert isinstance(result.artifacts, list)

    @staticmethod
    def assert_valid_adapter_result(result: AdapterResult):
        """Assert that adapter result is valid."""
        assert isinstance(result, AdapterResult)
        assert isinstance(result.success, bool)
        assert isinstance(result.tokens_used, int)
        assert isinstance(result.artifacts, list)

    @staticmethod
    def assert_response_time(response_time: float, max_time: float):
        """Assert response time is within acceptable limits."""
        assert (
            response_time <= max_time
        ), f"Response time {response_time}s exceeds {max_time}s"


@pytest.fixture
def test_utils():
    """Test utilities instance."""
    return TestUtils()


# Performance Testing


class PerformanceMonitor:
    """Monitor performance during tests."""

    def __init__(self):
        self.metrics = {}
        self.start_time = None

    def start(self):
        """Start monitoring."""
        self.start_time = asyncio.get_event_loop().time()

    def record_metric(self, name: str, value: float):
        """Record a performance metric."""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)

    def get_duration(self) -> float:
        """Get total duration."""
        if self.start_time is None:
            return 0.0
        return asyncio.get_event_loop().time() - self.start_time

    def get_average(self, metric_name: str) -> float:
        """Get average for a metric."""
        values = self.metrics.get(metric_name, [])
        return sum(values) / len(values) if values else 0.0

    def assert_performance_targets(self, targets: Dict[str, float]):
        """Assert performance targets are met."""
        for metric, target in targets.items():
            actual = self.get_average(metric)
            assert actual <= target, f"{metric}: {actual} exceeds target {target}"


@pytest.fixture
def performance_monitor():
    """Performance monitoring fixture."""
    return PerformanceMonitor()


# Contract Testing


class ContractValidator:
    """Validate API and data contracts."""

    @staticmethod
    def validate_workflow_schema(workflow_data: Dict, schema_file: Path):
        """Validate workflow against schema."""
        try:
            import jsonschema

            with open(schema_file) as f:
                schema = json.load(f)

            jsonschema.validate(workflow_data, schema)

        except ImportError:
            pytest.skip("jsonschema not available for contract validation")
        except jsonschema.ValidationError as e:
            pytest.fail(f"Workflow schema validation failed: {e}")

    @staticmethod
    def validate_adapter_result_contract(result: AdapterResult):
        """Validate adapter result contract."""
        assert hasattr(result, "success")
        assert hasattr(result, "tokens_used")
        assert hasattr(result, "artifacts")
        assert hasattr(result, "output")
        assert hasattr(result, "error")
        assert hasattr(result, "metadata")

        # Type validation
        assert isinstance(result.success, bool)
        assert isinstance(result.tokens_used, int)
        assert isinstance(result.artifacts, list)
        assert result.output is None or isinstance(result.output, str)
        assert result.error is None or isinstance(result.error, str)
        assert isinstance(result.metadata, dict)


@pytest.fixture
def contract_validator():
    """Contract validation fixture."""
    return ContractValidator()


# Test Configuration


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "contract: Contract tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "slow: Slow tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    # Add default markers based on test location
    for item in items:
        test_path = str(item.fspath)
        if "unit" in test_path:
            item.add_marker(pytest.mark.unit)
        elif "integration" in test_path:
            item.add_marker(pytest.mark.integration)
        elif "e2e" in test_path:
            item.add_marker(pytest.mark.e2e)
        elif "contract" in test_path:
            item.add_marker(pytest.mark.contract)
        elif "performance" in test_path:
            item.add_marker(pytest.mark.performance)
        elif "security" in test_path:
            item.add_marker(pytest.mark.security)


# Coverage and Test Plugins
pytest_plugins = ["pytest_asyncio", "pytest_mock", "pytest_timeout"]
