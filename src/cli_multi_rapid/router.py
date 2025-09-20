#!/usr/bin/env python3
"""
CLI Orchestrator Router System

Routes workflow steps between deterministic tools and AI adapters based on
configured policies and step requirements.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rich.console import Console

console = Console()


@dataclass
class RoutingDecision:
    """Result of routing decision for a workflow step."""

    adapter_name: str
    adapter_type: str  # "deterministic" or "ai"
    reasoning: str
    estimated_tokens: int = 0


class Router:
    """Routes workflow steps to appropriate adapters."""

    def __init__(self):
        self.console = Console()
        self.adapters = self._initialize_adapters()

    def _initialize_adapters(self) -> Dict[str, Any]:
        """Initialize available adapters."""
        return {
            # Deterministic tool adapters
            "vscode_diagnostics": {
                "type": "deterministic",
                "description": "Run VS Code diagnostic analysis",
                "cost": 0,
                "available": True,
            },
            "code_fixers": {
                "type": "deterministic",
                "description": "Apply automated code fixes",
                "cost": 0,
                "available": True,
            },
            "pytest_runner": {
                "type": "deterministic",
                "description": "Execute Python tests",
                "cost": 0,
                "available": True,
            },
            "verifier": {
                "type": "deterministic",
                "description": "Validate artifacts and gates",
                "cost": 0,
                "available": True,
            },
            "git_ops": {
                "type": "deterministic",
                "description": "Git operations and PR creation",
                "cost": 0,
                "available": True,
            },
            # AI-powered adapters
            "ai_editor": {
                "type": "ai",
                "description": "AI-powered code editing",
                "cost": 1000,  # Estimated tokens
                "available": True,
            },
        }

    def route_step(
        self, step: Dict[str, Any], policy: Optional[Dict[str, Any]] = None
    ) -> RoutingDecision:
        """Route a workflow step to the appropriate adapter."""

        actor = step.get("actor", "unknown")
        step_name = step.get("name", "Unnamed step")

        # Check if actor is available
        if actor not in self.adapters:
            return RoutingDecision(
                adapter_name="fallback",
                adapter_type="ai",
                reasoning=f"Unknown actor '{actor}' - fallback to AI",
                estimated_tokens=500,
            )

        adapter_info = self.adapters[actor]

        # Check availability
        if not adapter_info.get("available", False):
            return RoutingDecision(
                adapter_name="fallback",
                adapter_type="ai",
                reasoning=f"Actor '{actor}' not available - fallback to AI",
                estimated_tokens=500,
            )

        # Apply routing policy
        prefer_deterministic = True
        if policy:
            prefer_deterministic = policy.get("prefer_deterministic", True)

        # Route based on adapter type and policy
        if adapter_info["type"] == "deterministic":
            return RoutingDecision(
                adapter_name=actor,
                adapter_type="deterministic",
                reasoning=f"Deterministic tool: {adapter_info['description']}",
                estimated_tokens=0,
            )
        elif adapter_info["type"] == "ai":
            if prefer_deterministic:
                # Check if there's a deterministic alternative
                alt_adapter = self._find_deterministic_alternative(actor)
                if alt_adapter:
                    return RoutingDecision(
                        adapter_name=alt_adapter,
                        adapter_type="deterministic",
                        reasoning=f"Policy prefers deterministic - using {alt_adapter} instead of {actor}",
                        estimated_tokens=0,
                    )

            return RoutingDecision(
                adapter_name=actor,
                adapter_type="ai",
                reasoning=f"AI tool: {adapter_info['description']}",
                estimated_tokens=adapter_info.get("cost", 1000),
            )

        # Fallback
        return RoutingDecision(
            adapter_name="fallback",
            adapter_type="ai",
            reasoning="Fallback routing due to configuration error",
            estimated_tokens=500,
        )

    def _find_deterministic_alternative(self, ai_actor: str) -> Optional[str]:
        """Find a deterministic alternative for an AI actor."""
        alternatives = {
            "ai_editor": "code_fixers",  # For simple fixes, prefer automated tools
        }
        return alternatives.get(ai_actor)

    def get_available_actors(self) -> List[str]:
        """Get list of all available actors."""
        return [
            name for name, info in self.adapters.items() if info.get("available", False)
        ]

    def estimate_workflow_cost(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate the total cost of executing a workflow."""
        steps = workflow.get("steps", [])
        policy = workflow.get("policy", {})

        total_tokens = 0
        deterministic_steps = 0
        ai_steps = 0

        for step in steps:
            decision = self.route_step(step, policy)
            total_tokens += decision.estimated_tokens

            if decision.adapter_type == "deterministic":
                deterministic_steps += 1
            else:
                ai_steps += 1

        return {
            "total_estimated_tokens": total_tokens,
            "deterministic_steps": deterministic_steps,
            "ai_steps": ai_steps,
            "estimated_cost_usd": total_tokens * 0.00001,  # Rough estimate
            "routing_decisions": len(steps),
        }
