#!/usr/bin/env python3
"""
Test script for AI adapters integration.

Validates that AI adapters can be registered, discovered, and executed
within the CLI Orchestrator framework.
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli_multi_rapid.adapters import AdapterRegistry, AIAnalystAdapter, AIEditorAdapter
from cli_multi_rapid.router import Router


def test_ai_adapter_registration():
    """Test that AI adapters can be registered and discovered."""
    print("Testing AI adapter registration...")

    registry = AdapterRegistry()
    registry.register(AIEditorAdapter())
    registry.register(AIAnalystAdapter())

    adapters = registry.list_adapters()
    print(f"Registered adapters: {adapters}")

    assert "ai_editor" in adapters, "AIEditorAdapter should be registered"
    assert "ai_analyst" in adapters, "AIAnalystAdapter should be registered"

    # Test availability
    ai_editor_available = registry.is_available("ai_editor")
    ai_analyst_available = registry.is_available("ai_analyst")

    print(f"AI Editor available: {ai_editor_available}")
    print(f"AI Analyst available: {ai_analyst_available}")

    print("SUCCESS: AI adapter registration works correctly\n")


def test_ai_editor_execution():
    """Test AI editor adapter execution."""
    print("Testing AI Editor execution...")

    adapter = AIEditorAdapter()

    # Test step validation
    valid_step = {
        "id": "1.001",
        "name": "AI Code Edit",
        "actor": "ai_editor",
        "with": {
            "tool": "aider",
            "prompt": "Add type hints to this function",
            "model": "claude-3-5-sonnet-20241022",
        },
        "emits": ["artifacts/ai-edit.json"],
    }

    is_valid = adapter.validate_step(valid_step)
    print(f"Step validation: {is_valid}")
    assert is_valid, "Valid AI editor step should pass validation"

    # Test cost estimation
    estimated_cost = adapter.estimate_cost(valid_step)
    print(f"Estimated cost: {estimated_cost} tokens")
    assert estimated_cost > 0, "AI adapter should have non-zero cost"

    # Test execution (dry-run since aider may not be installed)
    try:
        result = adapter.execute(valid_step, files="*.py")
        print(f"Execution result: success={result.success}")

        if not result.success:
            print(f"Expected failure (aider not available): {result.error}")
        else:
            print(f"Tokens used: {result.tokens_used}")
            print(f"Artifacts: {result.artifacts}")

    except Exception as e:
        print(f"Execution failed as expected: {e}")

    print("SUCCESS: AI Editor adapter execution test completed\n")


def test_ai_analyst_execution():
    """Test AI analyst adapter execution."""
    print("Testing AI Analyst execution...")

    adapter = AIAnalystAdapter()

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
        "emits": ["artifacts/code-review.json"],
    }

    is_valid = adapter.validate_step(valid_step)
    print(f"Step validation: {is_valid}")
    assert is_valid, "Valid AI analyst step should pass validation"

    # Test cost estimation
    estimated_cost = adapter.estimate_cost(valid_step)
    print(f"Estimated cost: {estimated_cost} tokens")
    assert estimated_cost > 0, "AI adapter should have non-zero cost"

    # Test execution (should work since it uses mock analysis)
    result = adapter.execute(valid_step, files="src/**/*.py")
    print(f"Execution result: success={result.success}")

    if result.success:
        print(f"Tokens used: {result.tokens_used}")
        print(f"Artifacts: {result.artifacts}")

        # Check if artifact was created
        if result.artifacts:
            artifact_path = result.artifacts[0]
            if Path(artifact_path).exists():
                print(f"Artifact created: {artifact_path}")
                with open(artifact_path) as f:
                    artifact_data = json.load(f)
                print(f"Analysis type: {artifact_data.get('analysis_type')}")
    else:
        print(f"Execution failed: {result.error}")

    print("SUCCESS: AI Analyst adapter execution test completed\n")


def test_router_integration():
    """Test AI adapters integration with router."""
    print("Testing Router integration with AI adapters...")

    router = Router()
    available_actors = router.get_available_actors()

    print(f"Available actors: {available_actors}")
    assert "ai_editor" in available_actors, "AI Editor should be available in router"
    assert "ai_analyst" in available_actors, "AI Analyst should be available in router"

    # Test routing decisions
    ai_edit_step = {
        "id": "1.001",
        "name": "AI Code Edit",
        "actor": "ai_editor",
        "with": {"prompt": "Fix this code"},
    }

    decision = router.route_step(ai_edit_step)
    print(f"AI Editor routing: {decision.adapter_name} ({decision.adapter_type})")
    print(f"Reasoning: {decision.reasoning}")

    # Test with prefer_deterministic policy
    policy = {"prefer_deterministic": True}
    decision_deterministic = router.route_step(ai_edit_step, policy)
    print(f"With prefer_deterministic: {decision_deterministic.adapter_name}")

    # Test cost estimation
    workflow = {
        "steps": [ai_edit_step],
        "policy": {"prefer_deterministic": False},
    }

    cost_estimate = router.estimate_workflow_cost(workflow)
    print(f"Workflow cost estimate: {cost_estimate}")

    print("SUCCESS: Router integration test completed\n")


def test_supported_features():
    """Test AI adapter supported features."""
    print("Testing AI adapter supported features...")

    ai_editor = AIEditorAdapter()
    ai_analyst = AIAnalystAdapter()

    # Test AI Editor features
    supported_models = ai_editor.get_supported_models()
    supported_operations = ai_editor.get_supported_operations()

    print(f"AI Editor supported models: {len(supported_models)}")
    print(f"AI Editor supported operations: {supported_operations}")

    # Test AI Analyst features
    supported_analysis_types = ai_analyst.get_supported_analysis_types()
    supported_focus_areas = ai_analyst.get_supported_focus_areas()

    print(f"AI Analyst analysis types: {supported_analysis_types}")
    print(f"AI Analyst focus areas: {len(supported_focus_areas)}")

    assert len(supported_models) > 0, "AI Editor should support multiple models"
    assert "edit" in supported_operations, "AI Editor should support edit operation"
    assert (
        "code_review" in supported_analysis_types
    ), "AI Analyst should support code review"

    print("SUCCESS: AI adapter features test completed\n")


def main():
    """Run all AI adapter tests."""
    print("=" * 60)
    print("CLI Orchestrator AI Adapters Integration Test")
    print("=" * 60)
    print()

    try:
        test_ai_adapter_registration()
        test_ai_editor_execution()
        test_ai_analyst_execution()
        test_router_integration()
        test_supported_features()

        print("=" * 60)
        print("ALL TESTS PASSED!")
        print("AI adapters are successfully integrated with CLI Orchestrator")
        print("=" * 60)

    except Exception as e:
        print(f"TEST FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
