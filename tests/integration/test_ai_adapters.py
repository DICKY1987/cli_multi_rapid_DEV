#!/usr/bin/env python3
"""
Integration tests for AI adapters in CLI Multi-Rapid.
Tests the AI-powered code analysis and editing functionality.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cli_multi_rapid.adapters import (
    AIAnalystAdapter,
    AIEditorAdapter,
    AdapterRegistry,
)
from cli_multi_rapid.router import Router


class TestAIAdaptersIntegration:
    """Integration tests for AI adapters."""

    def test_ai_adapter_discovery(self):
        """Test that AI adapters can be discovered and registered."""
        registry = AdapterRegistry()
        registry.register(AIEditorAdapter())
        registry.register(AIAnalystAdapter())

        adapters = registry.list_adapters()

        assert "ai_editor" in adapters
        assert "ai_analyst" in adapters

        # Check metadata
        available_adapters = registry.get_available_adapters()

        assert "ai_editor" in available_adapters
        assert "ai_analyst" in available_adapters

    def test_ai_editor_adapter(self):
        """Test AI editor adapter functionality."""
        adapter = AIEditorAdapter()

        # Test metadata
        assert adapter.name == "ai_editor"
        assert adapter.adapter_type.value == "ai"
        assert "AI-powered code editing" in adapter.description

        # Test step validation
        valid_step = {
            "id": "1.001",
            "name": "AI Code Edit",
            "actor": "ai_editor",
            "with": {
                "tool": "aider",
                "prompt": "Add type hints to functions",
                "model": "claude-3-5-sonnet-20241022",
            },
            "emits": ["artifacts/ai-edit.json"],
        }

        assert adapter.validate_step(valid_step)

        # Test invalid step (missing prompt)
        invalid_step = {
            "id": "1.001",
            "name": "Invalid AI Edit",
            "actor": "ai_editor",
            "with": {"tool": "aider"},
            "emits": [],
        }

        assert not adapter.validate_step(invalid_step)

        # Test cost estimation
        cost = adapter.estimate_cost(valid_step)
        assert cost > 0
        assert isinstance(cost, int)

        # Test supported features
        models = adapter.get_supported_models()
        operations = adapter.get_supported_operations()

        assert len(models) > 0
        assert "claude-3-5-sonnet-20241022" in models
        assert "edit" in operations
        assert "refactor" in operations

    def test_ai_analyst_adapter(self):
        """Test AI analyst adapter functionality."""
        adapter = AIAnalystAdapter()

        # Test metadata
        assert adapter.name == "ai_analyst"
        assert adapter.adapter_type.value == "ai"
        assert "AI-powered code analysis" in adapter.description

        # Test step validation
        valid_step = {
            "id": "1.002",
            "name": "Code Review",
            "actor": "ai_analyst",
            "with": {
                "analysis_type": "code_review",
                "focus_areas": ["quality", "bugs"],
                "detail_level": "medium",
            },
            "emits": ["artifacts/analysis.json"],
        }

        assert adapter.validate_step(valid_step)

        # Test invalid analysis type
        invalid_step = {
            "id": "1.002",
            "name": "Invalid Analysis",
            "actor": "ai_analyst",
            "with": {
                "analysis_type": "unsupported_type",
            },
            "emits": [],
        }

        assert not adapter.validate_step(invalid_step)

        # Test cost estimation
        cost = adapter.estimate_cost(valid_step)
        assert cost > 0
        assert isinstance(cost, int)

        # Test supported features
        analysis_types = adapter.get_supported_analysis_types()
        focus_areas = adapter.get_supported_focus_areas()

        assert "code_review" in analysis_types
        assert "architecture_analysis" in analysis_types
        assert "quality" in focus_areas
        assert "bugs" in focus_areas

    def test_ai_analyst_execution(self, tmp_path):
        """Test AI analyst execution with mock data."""
        adapter = AIAnalystAdapter()

        # Create test Python file
        test_file = tmp_path / "test_code.py"
        test_file.write_text('''
def example_function(data):
    """Example function for testing."""
    if data is None:
        return []

    results = []
    for item in data:
        if item is not None:
            results.append(str(item))

    return results
''')

        # Create artifacts directory
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        artifact_path = artifacts_dir / "test-analysis.json"

        step = {
            "id": "1.001",
            "name": "Test Code Review",
            "actor": "ai_analyst",
            "with": {
                "analysis_type": "code_review",
                "focus_areas": ["quality", "bugs"],
                "detail_level": "medium",
            },
            "emits": [str(artifact_path)],
        }

        # Execute analysis
        result = adapter.execute(step, files=str(test_file))

        assert result.success
        assert result.tokens_used > 0
        assert len(result.artifacts) > 0

        # Check that artifact was created
        assert artifact_path.exists()

        # Validate artifact content
        with open(artifact_path) as f:
            analysis_data = json.load(f)

        assert analysis_data["review_type"] == "code_review"
        assert "findings" in analysis_data
        assert "summary" in analysis_data

    def test_router_ai_integration(self):
        """Test AI adapters integration with router system."""
        router = Router()

        # Check that AI adapters are available
        available_actors = router.get_available_actors()
        assert "ai_editor" in available_actors
        assert "ai_analyst" in available_actors

        # Test routing decisions
        ai_step = {
            "id": "1.001",
            "name": "AI Analysis",
            "actor": "ai_analyst",
            "with": {"analysis_type": "code_review"},
        }

        # Test with prefer_deterministic=False (should use AI)
        policy_ai = {"prefer_deterministic": False}
        decision = router.route_step(ai_step, policy_ai)

        # Should route to AI analyst or fallback
        assert decision.adapter_type == "ai"
        assert decision.estimated_tokens > 0

        # Test with prefer_deterministic=True (should try deterministic alternative)
        policy_deterministic = {"prefer_deterministic": True}
        decision_det = router.route_step(ai_step, policy_deterministic)

        # Should try to use deterministic alternative
        if decision_det.adapter_name != "fallback":
            assert decision_det.adapter_type in ["deterministic", "ai"]

    def test_workflow_cost_estimation(self):
        """Test cost estimation for AI workflows."""
        router = Router()

        # Create sample AI workflow
        workflow = {
            "name": "AI Analysis Workflow",
            "policy": {"prefer_deterministic": False},
            "steps": [
                {
                    "id": "1.001",
                    "name": "Code Review",
                    "actor": "ai_analyst",
                    "with": {
                        "analysis_type": "code_review",
                        "detail_level": "high",
                    },
                },
                {
                    "id": "1.002",
                    "name": "AI Refactoring",
                    "actor": "ai_editor",
                    "with": {
                        "tool": "aider",
                        "prompt": "Refactor this code",
                        "max_tokens": 4000,
                    },
                },
            ],
        }

        # Estimate cost
        cost_estimate = router.estimate_workflow_cost(workflow)

        assert "total_estimated_tokens" in cost_estimate
        assert "ai_steps" in cost_estimate
        assert "estimated_cost_usd" in cost_estimate

        assert cost_estimate["total_estimated_tokens"] > 0
        assert cost_estimate["ai_steps"] >= 2  # Both steps should be AI
        assert cost_estimate["estimated_cost_usd"] > 0

    def test_ai_adapter_error_handling(self):
        """Test error handling in AI adapters."""
        ai_editor = AIEditorAdapter()
        ai_analyst = AIAnalystAdapter()

        # Test AI editor with invalid tool
        invalid_editor_step = {
            "id": "1.001",
            "name": "Invalid Tool",
            "actor": "ai_editor",
            "with": {
                "tool": "invalid_tool",
                "prompt": "Do something",
            },
            "emits": [],
        }

        result = ai_editor.execute(invalid_editor_step)
        assert not result.success
        assert "Unsupported AI tool" in result.error

        # Test AI analyst with invalid analysis type
        invalid_analyst_step = {
            "id": "1.001",
            "name": "Invalid Analysis",
            "actor": "ai_analyst",
            "with": {
                "analysis_type": "invalid_analysis",
            },
            "emits": [],
        }

        result = ai_analyst.execute(invalid_analyst_step)
        assert not result.success
        assert "Unsupported analysis type" in result.error

    def test_ai_adapter_availability(self):
        """Test AI adapter availability checks."""
        ai_editor = AIEditorAdapter()
        ai_analyst = AIAnalystAdapter()

        # AI Editor requires external tools (aider), may not be available
        editor_available = ai_editor.is_available()
        assert isinstance(editor_available, bool)

        # AI Analyst uses mock analysis, should always be available
        analyst_available = ai_analyst.is_available()
        assert analyst_available is True

    def test_different_analysis_types(self):
        """Test different AI analysis types."""
        adapter = AIAnalystAdapter()

        analysis_types = [
            "code_review",
            "architecture_analysis",
            "refactor_planning",
            "test_planning",
        ]

        for analysis_type in analysis_types:
            step = {
                "id": "1.001",
                "name": f"Test {analysis_type}",
                "actor": "ai_analyst",
                "with": {
                    "analysis_type": analysis_type,
                    "detail_level": "medium",
                },
                "emits": [f"artifacts/{analysis_type}.json"],
            }

            # Should validate successfully
            assert adapter.validate_step(step)

            # Should have reasonable cost estimate
            cost = adapter.estimate_cost(step)
            assert cost > 0

    @pytest.mark.slow
    def test_ai_workflow_simulation(self, tmp_path):
        """Simulate a complete AI workflow execution."""
        # Create test files
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()

        (test_dir / "main.py").write_text('''
def calculate_total(items):
    total = 0
    for item in items:
        if item > 0:
            total += item
    return total

def process_data(data):
    if data is None:
        return []
    return [x for x in data if x is not None]
''')

        # Create artifacts directory
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Initialize adapters
        ai_analyst = AIAnalystAdapter()

        # Step 1: Code Review
        review_step = {
            "id": "1.001",
            "name": "Code Review",
            "actor": "ai_analyst",
            "with": {
                "analysis_type": "code_review",
                "focus_areas": ["quality", "bugs"],
                "detail_level": "medium",
            },
            "emits": [str(artifacts_dir / "review.json")],
        }

        review_result = ai_analyst.execute(
            review_step,
            files=str(test_dir / "*.py")
        )

        assert review_result.success
        assert len(review_result.artifacts) > 0

        # Step 2: Architecture Analysis
        arch_step = {
            "id": "1.002",
            "name": "Architecture Analysis",
            "actor": "ai_analyst",
            "with": {
                "analysis_type": "architecture_analysis",
                "detail_level": "high",
            },
            "emits": [str(artifacts_dir / "architecture.json")],
        }

        arch_result = ai_analyst.execute(
            arch_step,
            files=str(test_dir / "*.py")
        )

        assert arch_result.success
        assert len(arch_result.artifacts) > 0

        # Verify total token usage
        total_tokens = review_result.tokens_used + arch_result.tokens_used
        assert total_tokens > 0

        print(f"Simulated AI workflow used {total_tokens} tokens")


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v"])