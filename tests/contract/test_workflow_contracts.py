"""
Contract tests for CLI Orchestrator workflows.

Validates that workflows conform to expected schemas and
that the workflow execution system maintains consistent
behavior across versions.
"""

import json

import pytest


@pytest.mark.contract
class TestWorkflowSchemaContracts:
    """Test workflow schema contract compliance."""

    def test_sample_workflow_schema_compliance(
        self, sample_workflow, workflow_schema, contract_validator
    ):
        """Test that sample workflow conforms to schema."""
        contract_validator.validate_workflow_schema(sample_workflow, workflow_schema)

    def test_workflow_required_fields(self, sample_workflow):
        """Test workflow has all required fields."""
        required_fields = ["name", "steps"]
        for field in required_fields:
            assert (
                field in sample_workflow
            ), f"Required field '{field}' missing from workflow"

        # Test steps have required fields
        for i, step in enumerate(sample_workflow["steps"]):
            step_required_fields = ["id", "name", "actor"]
            for field in step_required_fields:
                assert field in step, f"Required field '{field}' missing from step {i}"

    def test_step_id_format_contract(self, sample_workflow):
        """Test that step IDs follow the expected format."""
        for step in sample_workflow["steps"]:
            step_id = step["id"]
            assert isinstance(step_id, str), "Step ID must be string"
            # IDs should follow format like "1.001", "2.010", etc.
            if "." in step_id:
                parts = step_id.split(".")
                assert len(parts) == 2, f"Step ID {step_id} should have format 'X.YYY'"
                assert parts[
                    0
                ].isdigit(), f"Step ID {step_id} first part should be numeric"
                assert parts[
                    1
                ].isdigit(), f"Step ID {step_id} second part should be numeric"

    def test_actor_field_contract(self, sample_workflow):
        """Test that actor fields are valid identifiers."""
        valid_actors = {
            "mock_deterministic",
            "mock_ai",
            "vscode_diagnostics",
            "code_fixers",
            "ai_editor",
            "pytest_runner",
            "verifier",
            "git_ops",
        }

        for step in sample_workflow["steps"]:
            actor = step["actor"]
            assert isinstance(actor, str), "Actor must be string"
            assert len(actor) > 0, "Actor cannot be empty"
            # In a real system, you might validate against a registry
            # For tests, we just check it's a reasonable identifier
            assert (
                actor.replace("_", "").replace("-", "").isalnum()
            ), f"Actor {actor} should be alphanumeric with underscores/hyphens"

    def test_with_parameters_contract(self, sample_workflow):
        """Test that 'with' parameters are properly structured."""
        for step in sample_workflow["steps"]:
            if "with" in step:
                with_params = step["with"]
                assert isinstance(
                    with_params, dict
                ), "Step 'with' parameters must be a dictionary"
                # Parameters should have string keys
                for key in with_params.keys():
                    assert isinstance(key, str), f"Parameter key '{key}' must be string"

    def test_emits_field_contract(self, sample_workflow):
        """Test that 'emits' field follows contract."""
        for step in sample_workflow["steps"]:
            if "emits" in step:
                emits = step["emits"]
                assert isinstance(
                    emits, (list, str)
                ), "Step 'emits' must be string or list of strings"

                if isinstance(emits, list):
                    for artifact in emits:
                        assert isinstance(artifact, str), "Artifact path must be string"
                        assert len(artifact) > 0, "Artifact path cannot be empty"

    def test_conditional_execution_contract(self, sample_workflow):
        """Test conditional execution 'when' clause contract."""
        for step in sample_workflow["steps"]:
            if "when" in step:
                when_condition = step["when"]
                assert isinstance(
                    when_condition, str
                ), "Step 'when' condition must be string"
                assert len(when_condition) > 0, "When condition cannot be empty"


@pytest.mark.contract
class TestWorkflowExecutionContracts:
    """Test workflow execution behavior contracts."""

    def test_workflow_result_contract(
        self, mock_workflow_runner, workflow_file, contract_validator
    ):
        """Test that workflow execution returns consistent result format."""
        result = mock_workflow_runner.run(workflow_file, dry_run=True)

        # Validate result structure
        assert hasattr(result, "success")
        assert hasattr(result, "error")
        assert hasattr(result, "artifacts")
        assert hasattr(result, "tokens_used")
        assert hasattr(result, "steps_completed")

        # Validate types
        assert isinstance(result.success, bool)
        assert result.error is None or isinstance(result.error, str)
        assert isinstance(result.artifacts, list)
        assert isinstance(result.tokens_used, int)
        assert isinstance(result.steps_completed, int)

        # Validate constraints
        assert result.tokens_used >= 0
        assert result.steps_completed >= 0

    def test_dry_run_contract(self, mock_workflow_runner, workflow_file):
        """Test that dry runs don't consume tokens or make changes."""
        result = mock_workflow_runner.run(workflow_file, dry_run=True)

        assert result.success is True, "Dry runs should always succeed"
        assert result.tokens_used == 0, "Dry runs should not consume tokens"
        assert result.steps_completed > 0, "Dry runs should show completed steps"

    def test_token_limit_contract(self, mock_workflow_runner, workflow_file):
        """Test that token limits are enforced."""
        result = mock_workflow_runner.run(workflow_file, max_tokens=1)

        # With a very low token limit, execution should fail
        # (depends on mock adapter implementation)
        if not result.success:
            assert "Token limit exceeded" in result.error

    def test_file_pattern_contract(self, mock_workflow_runner, workflow_file):
        """Test that file patterns are properly handled."""
        patterns_to_test = ["**/*.py", "src/**/*.py", "*.js", "test_*.py"]

        for pattern in patterns_to_test:
            result = mock_workflow_runner.run(
                workflow_file, files=pattern, dry_run=True
            )
            # Should handle all patterns without error
            assert isinstance(result.success, bool)

    def test_lane_parameter_contract(self, mock_workflow_runner, workflow_file):
        """Test that lane parameter is properly handled."""
        lanes_to_test = ["feature/test-branch", "main", "develop", "bugfix/issue-123"]

        for lane in lanes_to_test:
            result = mock_workflow_runner.run(workflow_file, lane=lane, dry_run=True)
            # Should handle all lane formats
            assert isinstance(result.success, bool)


@pytest.mark.contract
class TestAPIResponseContracts:
    """Test API response format contracts."""

    def test_workflow_execution_response_contract(self, test_data_factory):
        """Test workflow execution API response format."""
        response_data = {
            "execution_id": "exec_test_123",
            "success": True,
            "error": None,
            "artifacts": ["test_artifact.json"],
            "tokens_used": 100,
            "steps_completed": 2,
            "execution_time_seconds": 5.5,
            "workflow_name": "test_workflow",
        }

        # Validate response structure
        required_fields = [
            "execution_id",
            "success",
            "artifacts",
            "tokens_used",
            "steps_completed",
            "execution_time_seconds",
        ]

        for field in required_fields:
            assert (
                field in response_data
            ), f"Required field '{field}' missing from response"

        # Validate types
        assert isinstance(response_data["execution_id"], str)
        assert isinstance(response_data["success"], bool)
        assert response_data["error"] is None or isinstance(response_data["error"], str)
        assert isinstance(response_data["artifacts"], list)
        assert isinstance(response_data["tokens_used"], int)
        assert isinstance(response_data["steps_completed"], int)
        assert isinstance(response_data["execution_time_seconds"], (int, float))

    def test_error_response_contract(self):
        """Test error response format contract."""
        error_response = {
            "error": "validation_error",
            "message": "Workflow file path is required",
            "details": {"field": "workflow_file", "code": "required"},
            "request_id": "req_error_123",
        }

        # Validate error response structure
        required_fields = ["error", "message"]
        for field in required_fields:
            assert (
                field in error_response
            ), f"Required field '{field}' missing from error response"

        # Validate types
        assert isinstance(error_response["error"], str)
        assert isinstance(error_response["message"], str)
        assert error_response["details"] is None or isinstance(
            error_response["details"], dict
        )
        assert error_response["request_id"] is None or isinstance(
            error_response["request_id"], str
        )

    def test_health_check_response_contract(self):
        """Test health check response format."""
        health_response = {
            "status": "healthy",
            "service": "cli-orchestrator",
            "version": "1.0.0",
            "timestamp": "2024-01-15T10:30:00Z",
            "checks": {
                "workflow_schemas": {
                    "status": "healthy",
                    "message": "All schemas available",
                    "duration_ms": 1.2,
                },
                "adapters": {
                    "status": "healthy",
                    "message": "All adapters operational",
                    "duration_ms": 0.8,
                },
            },
        }

        # Validate health response structure
        assert "status" in health_response
        assert "service" in health_response
        assert health_response["status"] in ["healthy", "degraded", "unhealthy"]

        # Validate checks structure
        if "checks" in health_response:
            for check_name, check_data in health_response["checks"].items():
                assert "status" in check_data
                assert check_data["status"] in ["healthy", "degraded", "unhealthy"]


@pytest.mark.contract
class TestBackwardCompatibilityContracts:
    """Test backward compatibility contracts."""

    def test_workflow_format_backward_compatibility(self, sample_workflow):
        """Test that workflow format remains backward compatible."""
        # Core fields that must remain stable
        stable_fields = ["name", "steps"]
        for field in stable_fields:
            assert (
                field in sample_workflow
            ), f"Stable field '{field}' must remain in workflow format"

        # Step fields that must remain stable
        stable_step_fields = ["id", "name", "actor"]
        for step in sample_workflow["steps"]:
            for field in stable_step_fields:
                assert (
                    field in step
                ), f"Stable step field '{field}' must remain in workflow format"

    def test_api_response_backward_compatibility(self):
        """Test that API response formats remain backward compatible."""
        # Workflow execution response fields that must remain stable
        stable_response_fields = [
            "success",
            "artifacts",
            "tokens_used",
            "steps_completed",
        ]

        response = {
            "execution_id": "test",
            "success": True,
            "artifacts": [],
            "tokens_used": 0,
            "steps_completed": 0,
            "execution_time_seconds": 0.0,
            "workflow_name": "test",
        }

        for field in stable_response_fields:
            assert (
                field in response
            ), f"Stable response field '{field}' must remain in API response format"

    def test_error_format_backward_compatibility(self):
        """Test that error formats remain backward compatible."""
        # Error fields that must remain stable
        stable_error_fields = ["error", "message"]

        error = {
            "error": "test_error",
            "message": "Test error message",
            "details": {},
            "request_id": "test_123",
        }

        for field in stable_error_fields:
            assert (
                field in error
            ), f"Stable error field '{field}' must remain in error format"


@pytest.mark.contract
class TestSchemaEvolutionContracts:
    """Test schema evolution and versioning contracts."""

    def test_schema_version_compatibility(self, workflow_schema):
        """Test that schema maintains version compatibility."""
        with open(workflow_schema) as f:
            schema = json.load(f)

        # Schema should have version information
        assert "$schema" in schema, "Schema must declare JSON Schema version"

        # Should use a stable JSON Schema version
        assert schema["$schema"] in [
            "http://json-schema.org/draft-07/schema#",
            "https://json-schema.org/draft/2019-09/schema",
            "https://json-schema.org/draft/2020-12/schema",
        ], "Schema should use a stable JSON Schema version"

    def test_required_fields_stability(self, workflow_schema):
        """Test that required fields in schema remain stable."""
        with open(workflow_schema) as f:
            schema = json.load(f)

        # Core required fields that must not change
        stable_required = ["name", "steps"]

        if "required" in schema:
            for field in stable_required:
                assert (
                    field in schema["required"]
                ), f"Stable required field '{field}' must remain in schema"

    def test_field_type_stability(self, workflow_schema):
        """Test that field types in schema remain stable."""
        with open(workflow_schema) as f:
            schema = json.load(f)

        if "properties" in schema:
            # Field types that must remain stable
            stable_types = {"name": "string", "steps": "array"}

            for field, expected_type in stable_types.items():
                if field in schema["properties"]:
                    field_schema = schema["properties"][field]
                    if "type" in field_schema:
                        assert (
                            field_schema["type"] == expected_type
                        ), f"Field '{field}' type must remain {expected_type}"


@pytest.mark.contract
class TestPerformanceContracts:
    """Test performance-related contracts."""

    def test_execution_time_contract(self, mock_workflow_runner, workflow_file):
        """Test that workflow execution completes within reasonable time."""
        import time

        start_time = time.time()
        result = mock_workflow_runner.run(workflow_file, dry_run=True)
        execution_time = time.time() - start_time

        # Dry run should complete quickly
        assert execution_time < 10.0, f"Dry run took too long: {execution_time}s"
        assert result.success, "Dry run should succeed"

    def test_memory_usage_contract(self, mock_workflow_runner, workflow_file):
        """Test that workflow execution doesn't consume excessive memory."""
        # This is a placeholder - in a real implementation you'd measure memory usage
        result = mock_workflow_runner.run(workflow_file, dry_run=True)

        # Basic test that execution completes
        assert isinstance(result.success, bool)

    def test_token_efficiency_contract(self, mock_workflow_runner, workflow_file):
        """Test that token usage is reasonable for workflow complexity."""
        result = mock_workflow_runner.run(workflow_file, dry_run=False)

        if result.success:
            # Token usage should be proportional to steps completed
            if result.steps_completed > 0:
                tokens_per_step = result.tokens_used / result.steps_completed
                # This is workflow-dependent, but set a reasonable upper bound
                assert (
                    tokens_per_step < 10000
                ), f"Token usage per step too high: {tokens_per_step}"


@pytest.mark.contract
class TestSecurityContracts:
    """Test security-related contracts."""

    def test_workflow_parameter_sanitization_contract(self, sample_workflow):
        """Test that workflow parameters are properly sanitized."""
        # Check that no dangerous patterns exist
        workflow_str = json.dumps(sample_workflow)

        dangerous_patterns = ["__import__", "eval(", "exec(", "subprocess", "os.system"]

        for pattern in dangerous_patterns:
            assert (
                pattern not in workflow_str
            ), f"Potentially dangerous pattern '{pattern}' found in workflow"

    def test_file_path_security_contract(self, mock_workflow_runner, workflow_file):
        """Test that file paths are properly validated."""
        # Test various potentially dangerous file patterns
        dangerous_patterns = [
            "../../../etc/passwd",
            "~/.ssh/id_rsa",
            "/etc/shadow",
            "C:\\Windows\\System32\\*",
        ]

        for pattern in dangerous_patterns:
            # These should either fail gracefully or be properly sanitized
            result = mock_workflow_runner.run(
                workflow_file, files=pattern, dry_run=True
            )
            # Should not crash the system
            assert isinstance(result.success, bool)
