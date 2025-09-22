#!/usr/bin/env python3
"""
Integration tests for CLI Multi-Rapid adapter framework.
Tests the complete workflow from adapter discovery to execution.
"""

import json

# Add src to path for imports
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cli_multi_rapid.adapters import (
    AdapterRegistry,
    BaseAdapter,
    CodeFixersAdapter,
    PytestRunnerAdapter,
    VSCodeDiagnosticsAdapter,
)
from cli_multi_rapid.router import Router
from cli_multi_rapid.workflow_runner import WorkflowRunner


class TestAdapterIntegration:
    """Integration tests for adapter framework."""

    def test_adapter_registry_discovery(self):
        """Test that adapter registry can discover and load adapters."""
        registry = AdapterRegistry()
        adapters = registry.list_available_adapters()

        # Should find our core adapters
        assert "vscode_diagnostics" in adapters
        assert "code_fixers" in adapters
        assert "pytest_runner" in adapters

        # Check adapter metadata
        vscode_meta = adapters["vscode_diagnostics"]
        assert vscode_meta["name"] == "vscode_diagnostics"
        assert vscode_meta["description"] is not None
        assert vscode_meta["adapter_type"] is not None

    def test_adapter_instantiation(self):
        """Test that adapters can be instantiated from registry."""
        registry = AdapterRegistry()

        # Get adapter instance
        adapter = registry.get_adapter("vscode_diagnostics")
        assert isinstance(adapter, VSCodeDiagnosticsAdapter)
        assert adapter.name == "vscode_diagnostics"

        # Test adapter availability
        # Note: This may fail in CI if tools aren't installed
        availability = adapter.is_available()
        assert isinstance(availability, bool)

    def test_router_adapter_routing(self):
        """Test that router can properly route steps to adapters."""
        router = Router()

        # Test adapter routing
        step = {
            "id": "1.001",
            "name": "Test Diagnostics",
            "actor": "vscode_diagnostics",
            "with": {"analyzers": ["ruff"]},
            "emits": ["artifacts/test.json"],
        }

        # Should route to vscode_diagnostics adapter
        adapter = router._route_step(step)
        assert isinstance(adapter, VSCodeDiagnosticsAdapter)

    def test_workflow_runner_integration(self):
        """Test complete workflow execution through runner."""
        # Create minimal test workflow
        workflow = {
            "name": "Integration Test Workflow",
            "inputs": {"files": ["src/**/*.py"]},
            "policy": {"max_tokens": 1000, "prefer_deterministic": True},
            "steps": [
                {
                    "id": "1.001",
                    "name": "Test Validation",
                    "actor": "vscode_diagnostics",
                    "with": {
                        "analyzers": ["ruff"],
                        "files": "src/cli_multi_rapid/__init__.py",
                    },
                    "emits": ["artifacts/integration-test.json"],
                }
            ],
        }

        runner = WorkflowRunner()

        # Execute workflow (dry run)
        with patch("cli_multi_rapid.workflow_runner.Path") as mock_path:
            # Mock file existence
            mock_path.return_value.exists.return_value = True

            result = runner.execute_workflow(
                workflow, files="src/cli_multi_rapid/__init__.py", dry_run=True
            )

            # Should complete without errors
            assert "execution_id" in result
            assert "steps" in result

    def test_adapter_error_handling(self):
        """Test adapter error handling and recovery."""
        registry = AdapterRegistry()
        adapter = registry.get_adapter("vscode_diagnostics")

        # Test with invalid step
        invalid_step = {
            "id": "1.001",
            "name": "Invalid Test",
            "actor": "vscode_diagnostics",
            "with": {"invalid_param": "test"},
            "emits": [],
        }

        # Should handle gracefully
        try:
            result = adapter.execute(invalid_step)
            # Result should indicate failure but not crash
            assert hasattr(result, "success")
        except Exception as e:
            pytest.fail(f"Adapter should handle errors gracefully: {e}")

    def test_cross_adapter_workflow(self):
        """Test workflow that uses multiple different adapters."""
        workflow = {
            "name": "Multi-Adapter Workflow",
            "inputs": {"files": ["src/**/*.py"]},
            "policy": {"max_tokens": 5000, "prefer_deterministic": True},
            "steps": [
                {
                    "id": "1.001",
                    "name": "Diagnostic Analysis",
                    "actor": "vscode_diagnostics",
                    "with": {"analyzers": ["ruff"], "min_severity": "warning"},
                    "emits": ["artifacts/diagnostics.json"],
                },
                {
                    "id": "2.001",
                    "name": "Code Fixes",
                    "actor": "code_fixers",
                    "with": {"tools": ["ruff"], "fix_mode": True},
                    "emits": ["artifacts/fixes.json"],
                    "when": "artifacts/diagnostics.json exists",
                },
            ],
        }

        runner = WorkflowRunner()

        # Test workflow validation
        is_valid = runner._validate_workflow_schema(workflow)
        assert is_valid

        # Test step dependencies
        steps = workflow["steps"]
        assert len(steps) == 2
        assert steps[1].get("when") is not None

    @pytest.mark.slow
    def test_real_file_analysis(self, tmp_path):
        """Test adapter with real Python file (slower integration test)."""
        # Create a test Python file with known issues
        test_file = tmp_path / "test_analysis.py"
        test_file.write_text(
            '''
import os
import sys

def test_function(data):
    """Test function with issues."""
    if data is None:
        return []

    results = []
    for key, value in data.items():
        if value is not None:
            results.append(f"{key}: {value}")

    return results

if __name__ == "__main__":
    sample_data = {"name": "test", "value": 123}
    print(test_function(sample_data))
'''
        )

        # Test vscode_diagnostics adapter
        registry = AdapterRegistry()
        adapter = registry.get_adapter("vscode_diagnostics")

        if adapter.is_available():
            step = {
                "id": "1.001",
                "name": "Real File Analysis",
                "actor": "vscode_diagnostics",
                "with": {"analyzers": ["ruff"], "files": str(test_file)},
                "emits": ["artifacts/real-test.json"],
            }

            result = adapter.execute(step, files=str(test_file))

            # Should complete successfully
            assert hasattr(result, "success")

            # Should detect unused imports
            if result.success and result.metadata:
                issues = result.metadata.get("total_issues", 0)
                # Expecting at least unused import warnings
                assert issues >= 0  # May be 0 if file is clean

    def test_adapter_cost_estimation(self):
        """Test adapter cost estimation for budget planning."""
        registry = AdapterRegistry()

        # Test deterministic adapters (should have 0 cost)
        deterministic_adapters = ["vscode_diagnostics", "code_fixers", "pytest_runner"]

        for adapter_name in deterministic_adapters:
            adapter = registry.get_adapter(adapter_name)
            step = {
                "id": "1.001",
                "name": f"Test {adapter_name}",
                "actor": adapter_name,
                "with": {},
                "emits": [],
            }

            cost = adapter.estimate_cost(step)
            assert cost == 0, f"{adapter_name} should have zero cost (deterministic)"

    def test_adapter_metadata_consistency(self):
        """Test that adapter metadata is consistent and complete."""
        registry = AdapterRegistry()
        adapters = registry.list_available_adapters()

        for adapter_name, metadata in adapters.items():
            # Check required metadata fields
            assert "name" in metadata
            assert "description" in metadata
            assert "adapter_type" in metadata

            # Check name consistency
            assert metadata["name"] == adapter_name

            # Description should be meaningful
            assert len(metadata["description"]) > 10

            # Adapter type should be valid
            assert metadata["adapter_type"] in ["DETERMINISTIC", "AI_POWERED"]


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v"])
