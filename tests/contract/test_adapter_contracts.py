"""
Contract tests for CLI Orchestrator adapters.

Validates that all adapters conform to the expected interfaces
and contract specifications, ensuring compatibility and
preventing breaking changes.
"""


import pytest

from src.cli_multi_rapid.adapters.base_adapter import (
    AdapterResult,
    AdapterType,
    BaseAdapter,
)


@pytest.mark.contract
class TestBaseAdapterContract:
    """Test BaseAdapter interface contracts."""

    def test_base_adapter_is_abstract(self):
        """Test that BaseAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseAdapter("test", AdapterType.DETERMINISTIC, "test")

    def test_adapter_result_structure(self):
        """Test AdapterResult has all required fields."""
        result = AdapterResult(success=True)

        # Check all required fields exist
        assert hasattr(result, "success")
        assert hasattr(result, "tokens_used")
        assert hasattr(result, "artifacts")
        assert hasattr(result, "output")
        assert hasattr(result, "error")
        assert hasattr(result, "metadata")

        # Check default values
        assert result.success is True
        assert result.tokens_used == 0
        assert result.artifacts == []
        assert result.output is None
        assert result.error is None
        assert result.metadata == {}

    def test_adapter_result_to_dict(self):
        """Test AdapterResult to_dict() conversion."""
        result = AdapterResult(
            success=True,
            tokens_used=100,
            artifacts=["test.json"],
            output="Test output",
            error=None,
            metadata={"test": "value"},
        )

        result_dict = result.to_dict()

        expected_keys = {
            "success",
            "tokens_used",
            "artifacts",
            "output",
            "error",
            "metadata",
        }
        assert set(result_dict.keys()) == expected_keys

        assert result_dict["success"] is True
        assert result_dict["tokens_used"] == 100
        assert result_dict["artifacts"] == ["test.json"]
        assert result_dict["output"] == "Test output"
        assert result_dict["error"] is None
        assert result_dict["metadata"] == {"test": "value"}

    def test_adapter_result_to_dict_with_none_output(self):
        """Test AdapterResult to_dict() with None output."""
        result = AdapterResult(success=True, output=None)
        result_dict = result.to_dict()

        # Should convert None output to empty string
        assert result_dict["output"] == ""

    def test_adapter_types_enum(self):
        """Test AdapterType enum values."""
        assert AdapterType.DETERMINISTIC.value == "deterministic"
        assert AdapterType.AI.value == "ai"

        # Test all enum members
        adapter_types = list(AdapterType)
        assert len(adapter_types) == 2
        assert AdapterType.DETERMINISTIC in adapter_types
        assert AdapterType.AI in adapter_types


@pytest.mark.contract
class TestConcreteAdapterContract:
    """Test contracts for concrete adapter implementations."""

    def test_mock_deterministic_adapter_contract(
        self, mock_adapters, contract_validator
    ):
        """Test mock deterministic adapter conforms to contract."""
        adapter = mock_adapters["mock_deterministic"]

        # Check adapter properties
        assert isinstance(adapter, BaseAdapter)
        assert adapter.name == "mock_deterministic"
        assert adapter.adapter_type == AdapterType.DETERMINISTIC
        assert isinstance(adapter.description, str)

        # Check required methods exist
        assert hasattr(adapter, "execute")
        assert hasattr(adapter, "validate_step")
        assert hasattr(adapter, "estimate_cost")
        assert callable(adapter.execute)
        assert callable(adapter.validate_step)
        assert callable(adapter.estimate_cost)

    def test_mock_ai_adapter_contract(self, mock_adapters, contract_validator):
        """Test mock AI adapter conforms to contract."""
        adapter = mock_adapters["mock_ai"]

        # Check adapter properties
        assert isinstance(adapter, BaseAdapter)
        assert adapter.name == "mock_ai"
        assert adapter.adapter_type == AdapterType.AI
        assert isinstance(adapter.description, str)

        # Check required methods exist
        assert hasattr(adapter, "execute")
        assert hasattr(adapter, "validate_step")
        assert hasattr(adapter, "estimate_cost")

    def test_adapter_execute_method_contract(self, mock_adapters):
        """Test adapter execute method contract."""
        for adapter_name, adapter in mock_adapters.items():
            # Test step parameter
            step = {"id": "test", "name": "Test", "actor": adapter_name}

            result = adapter.execute(step)

            # Result must be AdapterResult instance
            assert isinstance(result, AdapterResult)

            # Test with optional parameters
            result = adapter.execute(step, context={"test": "value"})
            assert isinstance(result, AdapterResult)

            result = adapter.execute(step, files="**/*.py")
            assert isinstance(result, AdapterResult)

            result = adapter.execute(step, context={"test": "value"}, files="**/*.py")
            assert isinstance(result, AdapterResult)

    def test_adapter_validate_step_method_contract(self, mock_adapters):
        """Test adapter validate_step method contract."""
        for adapter_name, adapter in mock_adapters.items():
            step = {"id": "test", "name": "Test", "actor": adapter_name}

            result = adapter.validate_step(step)

            # Must return boolean
            assert isinstance(result, bool)

    def test_adapter_estimate_cost_method_contract(self, mock_adapters):
        """Test adapter estimate_cost method contract."""
        for adapter_name, adapter in mock_adapters.items():
            step = {"id": "test", "name": "Test", "actor": adapter_name}

            result = adapter.estimate_cost(step)

            # Must return integer
            assert isinstance(result, int)
            assert result >= 0

    def test_adapter_metadata_contract(self, mock_adapters):
        """Test adapter get_metadata method contract."""
        for adapter_name, adapter in mock_adapters.items():
            metadata = adapter.get_metadata()

            # Must be dictionary with required fields
            assert isinstance(metadata, dict)
            assert "type" in metadata
            assert "description" in metadata
            assert "cost" in metadata
            assert "available" in metadata

            # Type must match adapter_type
            assert metadata["type"] == adapter.adapter_type.value
            assert isinstance(metadata["description"], str)
            assert isinstance(metadata["cost"], int)
            assert isinstance(metadata["available"], bool)


@pytest.mark.contract
class TestWorkflowStepContract:
    """Test workflow step contract validation."""

    def test_valid_step_structure(self, mock_adapters):
        """Test valid step structure."""
        valid_step = {
            "id": "1.001",
            "name": "Test Step",
            "actor": "mock_deterministic",
            "with": {"param": "value"},
            "emits": ["output.json"],
        }

        adapter = mock_adapters["mock_deterministic"]

        # Should validate successfully
        assert adapter.validate_step(valid_step) is True

    def test_minimal_step_structure(self, mock_adapters):
        """Test minimal valid step structure."""
        minimal_step = {
            "id": "1.001",
            "name": "Test Step",
            "actor": "mock_deterministic",
        }

        adapter = mock_adapters["mock_deterministic"]

        # Should validate successfully with minimal fields
        result = adapter.validate_step(minimal_step)
        assert isinstance(result, bool)

    def test_step_with_conditional_execution(self, mock_adapters):
        """Test step with 'when' condition."""
        conditional_step = {
            "id": "1.002",
            "name": "Conditional Step",
            "actor": "mock_deterministic",
            "when": "success(1.001)",
        }

        adapter = mock_adapters["mock_deterministic"]
        result = adapter.validate_step(conditional_step)
        assert isinstance(result, bool)

    def test_step_with_dependencies(self, mock_adapters):
        """Test step with dependencies."""
        step_with_deps = {
            "id": "1.003",
            "name": "Step With Dependencies",
            "actor": "mock_deterministic",
            "depends_on": ["1.001", "1.002"],
        }

        adapter = mock_adapters["mock_deterministic"]
        result = adapter.validate_step(step_with_deps)
        assert isinstance(result, bool)


@pytest.mark.contract
class TestAdapterExecutionContract:
    """Test adapter execution behavior contracts."""

    def test_deterministic_adapter_execution_contract(self, mock_adapters):
        """Test deterministic adapter execution contract."""
        adapter = mock_adapters["mock_deterministic"]
        step = {"id": "test", "name": "Test", "actor": "mock_deterministic"}

        result = adapter.execute(step)

        # Deterministic adapters should use 0 tokens
        assert result.tokens_used == 0
        assert result.success is True
        assert isinstance(result.artifacts, list)
        assert result.output is not None

    def test_ai_adapter_execution_contract(self, mock_adapters):
        """Test AI adapter execution contract."""
        adapter = mock_adapters["mock_ai"]
        step = {"id": "test", "name": "Test", "actor": "mock_ai"}

        result = adapter.execute(step)

        # AI adapters should use tokens
        assert result.tokens_used > 0
        assert result.success is True
        assert isinstance(result.artifacts, list)
        assert result.output is not None

    def test_adapter_error_handling_contract(self, mock_adapters):
        """Test adapter error handling contract."""
        # This would test error conditions, but our mock adapters
        # always succeed. In a real implementation, you would test:
        # - Invalid step parameters
        # - Network failures (for AI adapters)
        # - Tool failures (for deterministic adapters)
        # - Timeout handling

        for adapter_name, adapter in mock_adapters.items():
            # Test with empty step
            result = adapter.execute({})

            # Should still return AdapterResult (may be success=False)
            assert isinstance(result, AdapterResult)


@pytest.mark.contract
class TestWorkflowResultContract:
    """Test WorkflowResult contract validation."""

    def test_workflow_result_structure(self, test_data_factory):
        """Test WorkflowResult has required structure."""
        result = test_data_factory.create_workflow_result()

        # Check all required fields
        assert hasattr(result, "success")
        assert hasattr(result, "error")
        assert hasattr(result, "artifacts")
        assert hasattr(result, "tokens_used")
        assert hasattr(result, "steps_completed")

        # Check types
        assert isinstance(result.success, bool)
        assert result.error is None or isinstance(result.error, str)
        assert isinstance(result.artifacts, list)
        assert isinstance(result.tokens_used, int)
        assert isinstance(result.steps_completed, int)

    def test_workflow_result_success_contract(self, test_data_factory):
        """Test successful WorkflowResult contract."""
        result = test_data_factory.create_workflow_result(success=True)

        assert result.success is True
        assert result.error is None
        assert result.tokens_used >= 0
        assert result.steps_completed >= 0
        assert isinstance(result.artifacts, list)

    def test_workflow_result_failure_contract(self, test_data_factory):
        """Test failed WorkflowResult contract."""
        result = test_data_factory.create_workflow_result(
            success=False, error="Test error message"
        )

        assert result.success is False
        assert isinstance(result.error, str)
        assert result.error != ""


@pytest.mark.contract
class TestContractBackwardCompatibility:
    """Test backward compatibility of contracts."""

    def test_adapter_result_backward_compatibility(self):
        """Test AdapterResult maintains backward compatibility."""
        # Test old-style creation (positional args)
        result = AdapterResult(
            True, 50, ["file.json"], "output", None, {"key": "value"}
        )

        assert result.success is True
        assert result.tokens_used == 50
        assert result.artifacts == ["file.json"]
        assert result.output == "output"
        assert result.error is None
        assert result.metadata == {"key": "value"}

    def test_adapter_result_dict_keys_compatibility(self):
        """Test AdapterResult dict keys remain stable."""
        result = AdapterResult(success=True)
        result_dict = result.to_dict()

        # These keys must remain stable for backward compatibility
        expected_keys = {
            "success",
            "tokens_used",
            "artifacts",
            "output",
            "error",
            "metadata",
        }

        assert set(result_dict.keys()) == expected_keys

    def test_adapter_interface_compatibility(self, mock_adapters):
        """Test adapter interface remains backward compatible."""
        for adapter_name, adapter in mock_adapters.items():
            # These method signatures must remain stable
            assert hasattr(adapter, "execute")
            assert hasattr(adapter, "validate_step")
            assert hasattr(adapter, "estimate_cost")
            assert hasattr(adapter, "get_metadata")
            assert hasattr(adapter, "is_available")
            assert hasattr(adapter, "supports_files")
            assert hasattr(adapter, "supports_with_params")

            # Core properties must exist
            assert hasattr(adapter, "name")
            assert hasattr(adapter, "adapter_type")
            assert hasattr(adapter, "description")
