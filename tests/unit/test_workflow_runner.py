"""
Unit tests for CLI Orchestrator WorkflowRunner.

Tests core workflow execution functionality including:
- Workflow loading and validation
- Step execution and routing
- Error handling and recovery
- Token usage tracking
"""

from unittest.mock import Mock, patch

import pytest

from src.cli_multi_rapid.adapters.base_adapter import AdapterResult
from src.cli_multi_rapid.workflow_runner import WorkflowRunner


class TestWorkflowRunner:
    """Test WorkflowRunner core functionality."""

    @pytest.fixture
    def runner(self):
        """Create WorkflowRunner instance."""
        return WorkflowRunner()

    def test_workflow_runner_initialization(self, runner):
        """Test WorkflowRunner initializes correctly."""
        assert runner is not None
        assert hasattr(runner, "console")

    def test_load_workflow_success(self, runner, workflow_file, sample_workflow):
        """Test successful workflow loading."""
        result = runner._load_workflow(workflow_file)

        assert result is not None
        assert result["name"] == sample_workflow["name"]
        assert result["version"] == sample_workflow["version"]
        assert len(result["steps"]) == len(sample_workflow["steps"])

    def test_load_workflow_missing_file(self, runner, temp_dir):
        """Test workflow loading with missing file."""
        missing_file = temp_dir / "missing.yaml"
        result = runner._load_workflow(missing_file)

        assert result is None

    def test_load_workflow_invalid_yaml(self, runner, temp_dir):
        """Test workflow loading with invalid YAML."""
        invalid_file = temp_dir / "invalid.yaml"
        invalid_file.write_text("invalid: yaml: content: [")

        result = runner._load_workflow(invalid_file)
        assert result is None

    def test_validate_schema_success(self, runner, sample_workflow, workflow_schema):
        """Test successful schema validation."""
        result = runner._validate_schema(sample_workflow)
        assert result is True

    def test_validate_schema_missing_schema_file(self, runner, sample_workflow):
        """Test schema validation with missing schema file."""
        # Should pass when schema file doesn't exist
        result = runner._validate_schema(sample_workflow)
        assert result is True

    @patch("src.cli_multi_rapid.workflow_runner.jsonschema")
    def test_validate_schema_invalid_workflow(
        self, mock_jsonschema, runner, sample_workflow
    ):
        """Test schema validation with invalid workflow."""
        # Mock jsonschema to raise ValidationError
        mock_jsonschema.validate.side_effect = Exception("Validation error")

        result = runner._validate_schema(sample_workflow)
        assert result is False

    def test_run_workflow_success(self, runner, workflow_file, mock_adapters):
        """Test successful workflow execution."""
        # Mock the router and adapter
        with patch.object(runner, "router") as mock_router:
            mock_router.route_step.return_value = Mock(
                adapter_name="mock_deterministic",
                reasoning="Test routing",
                estimated_tokens=50,
            )
            mock_router.registry.get_adapter.return_value = mock_adapters[
                "mock_deterministic"
            ]

            result = runner.run(workflow_file, dry_run=False)

            assert result.success is True
            assert result.steps_completed > 0
            assert result.tokens_used >= 0

    def test_run_workflow_dry_run(self, runner, workflow_file):
        """Test workflow dry run execution."""
        result = runner.run(workflow_file, dry_run=True)

        assert result.success is True
        assert result.tokens_used == 0
        assert result.steps_completed > 0

    def test_run_workflow_with_token_limit(self, runner, workflow_file, mock_adapters):
        """Test workflow execution with token limit."""
        with patch.object(runner, "router") as mock_router:
            # Mock adapter to return high token usage
            high_token_adapter = Mock()
            high_token_adapter.execute.return_value = AdapterResult(
                success=True,
                tokens_used=1500,  # High token usage
                artifacts=["output.json"],
            )
            high_token_adapter.validate_step.return_value = True

            mock_router.route_step.return_value = Mock(
                adapter_name="high_token_adapter",
                reasoning="High token routing",
                estimated_tokens=1500,
            )
            mock_router.registry.get_adapter.return_value = high_token_adapter

            result = runner.run(workflow_file, max_tokens=1000)

            assert result.success is False
            assert "Token limit exceeded" in result.error

    def test_run_workflow_missing_file(self, runner, temp_dir):
        """Test workflow execution with missing file."""
        missing_file = temp_dir / "missing.yaml"

        result = runner.run(missing_file)

        assert result.success is False
        assert "Failed to load workflow" in result.error

    def test_execute_step_success(self, runner, mock_adapters):
        """Test successful step execution."""
        step = {
            "id": "test_step",
            "name": "Test Step",
            "actor": "mock_deterministic",
            "with": {"param": "value"},
        }

        with patch.object(runner, "router") as mock_router:
            mock_router.route_step.return_value = Mock(
                adapter_name="mock_deterministic",
                reasoning="Test routing",
                estimated_tokens=0,
            )
            mock_router.registry.get_adapter.return_value = mock_adapters[
                "mock_deterministic"
            ]

            result = runner._execute_step(step)

            assert result["success"] is True
            assert result["tokens_used"] == 0
            assert len(result["artifacts"]) > 0

    def test_execute_step_adapter_not_available(self, runner):
        """Test step execution with unavailable adapter."""
        step = {"id": "test_step", "name": "Test Step", "actor": "unavailable_adapter"}

        with patch.object(runner, "router") as mock_router:
            mock_router.route_step.return_value = Mock(
                adapter_name="unavailable_adapter",
                reasoning="Routing to unavailable adapter",
                estimated_tokens=50,
            )
            mock_router.registry.get_adapter.return_value = None

            result = runner._execute_step(step)

            assert result["success"] is False
            assert "not available" in result["error"]

    def test_execute_step_validation_failure(self, runner, mock_adapters):
        """Test step execution with validation failure."""
        step = {
            "id": "test_step",
            "name": "Test Step",
            "actor": "mock_deterministic",
            "with": {"invalid": "params"},
        }

        # Mock adapter to fail validation
        mock_adapter = Mock()
        mock_adapter.validate_step.return_value = False

        with patch.object(runner, "router") as mock_router:
            mock_router.route_step.return_value = Mock(
                adapter_name="mock_deterministic",
                reasoning="Test routing",
                estimated_tokens=0,
            )
            mock_router.registry.get_adapter.return_value = mock_adapter

            result = runner._execute_step(step)

            assert result["success"] is False
            assert "validation failed" in result["error"]

    def test_execute_step_execution_exception(self, runner, mock_adapters):
        """Test step execution with adapter exception."""
        step = {"id": "test_step", "name": "Test Step", "actor": "mock_deterministic"}

        # Mock adapter to raise exception
        mock_adapter = Mock()
        mock_adapter.validate_step.return_value = True
        mock_adapter.execute.side_effect = Exception("Adapter execution failed")

        with patch.object(runner, "router") as mock_router:
            mock_router.route_step.return_value = Mock(
                adapter_name="mock_deterministic",
                reasoning="Test routing",
                estimated_tokens=50,
            )
            mock_router.registry.get_adapter.return_value = mock_adapter

            result = runner._execute_step(step)

            assert result["success"] is False
            assert "Adapter execution failed" in result["error"]

    def test_process_template_variables(self, runner, sample_workflow):
        """Test template variable processing."""
        # Add template variables to workflow
        workflow_with_templates = sample_workflow.copy()
        workflow_with_templates["inputs"]["files"] = "{{ inputs.files }}"
        workflow_with_templates["inputs"]["lane"] = "{{ inputs.lane }}"

        result = runner._process_template_variables(
            workflow_with_templates, files="src/**/*.py", lane="feature/test"
        )

        assert result["inputs"]["files"] == "src/**/*.py"
        assert result["inputs"]["lane"] == "feature/test"

    def test_should_execute_step_no_condition(self, runner):
        """Test step execution condition with no 'when' clause."""
        step = {"id": "test_step", "name": "Test Step", "actor": "mock_deterministic"}

        result = runner._should_execute_step(step, {})
        assert result is True

    def test_should_execute_step_with_condition(self, runner):
        """Test step execution condition with 'when' clause."""
        step = {
            "id": "test_step",
            "name": "Test Step",
            "actor": "mock_deterministic",
            "when": "success(previous_step)",
        }

        # Currently always returns True (placeholder implementation)
        result = runner._should_execute_step(step, {})
        assert result is True


@pytest.mark.integration
class TestWorkflowRunnerIntegration:
    """Integration tests for WorkflowRunner."""

    def test_full_workflow_execution_integration(self, runner, workflow_file, temp_dir):
        """Test complete workflow execution with file I/O."""
        # Create artifacts directory
        artifacts_dir = temp_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        # Mock router for integration test
        with patch.object(runner, "router") as mock_router:
            mock_adapter = Mock()
            mock_adapter.validate_step.return_value = True
            mock_adapter.execute.return_value = AdapterResult(
                success=True,
                tokens_used=25,
                artifacts=[str(artifacts_dir / "integration_test.json")],
                output="Integration test completed",
            )

            mock_router.route_step.return_value = Mock(
                adapter_name="integration_adapter",
                reasoning="Integration test routing",
                estimated_tokens=25,
            )
            mock_router.registry.get_adapter.return_value = mock_adapter

            result = runner.run(workflow_file)

            assert result.success is True
            assert result.steps_completed == 2  # Two steps in sample workflow
            assert result.tokens_used > 0


@pytest.mark.performance
class TestWorkflowRunnerPerformance:
    """Performance tests for WorkflowRunner."""

    def test_workflow_execution_performance(
        self, runner, workflow_file, performance_monitor
    ):
        """Test workflow execution performance."""
        performance_monitor.start()

        with patch.object(runner, "router") as mock_router:
            mock_adapter = Mock()
            mock_adapter.validate_step.return_value = True
            mock_adapter.execute.return_value = AdapterResult(
                success=True,
                tokens_used=10,
                artifacts=["perf_test.json"],
                output="Performance test",
            )

            mock_router.route_step.return_value = Mock(
                adapter_name="perf_adapter",
                reasoning="Performance test",
                estimated_tokens=10,
            )
            mock_router.registry.get_adapter.return_value = mock_adapter

            result = runner.run(workflow_file)

        execution_time = performance_monitor.get_duration()

        assert result.success is True
        assert execution_time < 5.0  # Should complete within 5 seconds

    def test_large_workflow_performance(
        self, runner, temp_dir, test_data_factory, performance_monitor
    ):
        """Test performance with large workflow."""
        # Create workflow with many steps
        large_workflow = test_data_factory.create_workflow_data()
        large_workflow["steps"] = [
            {
                "id": f"step_{i:03d}",
                "name": f"Step {i}",
                "actor": "mock_deterministic",
                "with": {"step_num": i},
            }
            for i in range(50)  # 50 steps
        ]

        workflow_file = temp_dir / "large_workflow.yaml"
        import yaml

        with open(workflow_file, "w") as f:
            yaml.dump(large_workflow, f)

        performance_monitor.start()

        with patch.object(runner, "router") as mock_router:
            mock_adapter = Mock()
            mock_adapter.validate_step.return_value = True
            mock_adapter.execute.return_value = AdapterResult(
                success=True, tokens_used=5, artifacts=[], output="Fast execution"
            )

            mock_router.route_step.return_value = Mock(
                adapter_name="fast_adapter",
                reasoning="Fast execution",
                estimated_tokens=5,
            )
            mock_router.registry.get_adapter.return_value = mock_adapter

            result = runner.run(workflow_file)

        execution_time = performance_monitor.get_duration()

        assert result.success is True
        assert result.steps_completed == 50
        assert execution_time < 10.0  # Should complete within 10 seconds
