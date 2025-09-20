#!/usr/bin/env python3
"""
CLI Orchestrator Router System

Routes workflow steps between deterministic tools and AI adapters based on
configured policies and step requirements.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rich.console import Console

from .adapters import AdapterRegistry
from .adapters.ai_analyst import AIAnalystAdapter
from .adapters.ai_editor import AIEditorAdapter
from .adapters.code_fixers import CodeFixersAdapter
from .adapters.pytest_runner import PytestRunnerAdapter
from .adapters.vscode_diagnostics import VSCodeDiagnosticsAdapter

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
        self.registry = AdapterRegistry()
        self._initialize_adapters()
        self.adapters = self.registry.get_available_adapters()

    def _initialize_adapters(self) -> None:
        """Initialize available adapters in the registry."""
        # Register deterministic adapters
        self.registry.register(CodeFixersAdapter())
        self.registry.register(PytestRunnerAdapter())
        self.registry.register(VSCodeDiagnosticsAdapter())

        # Register AI-powered adapters
        self.registry.register(AIEditorAdapter())
        self.registry.register(AIAnalystAdapter())

        # TODO: Register additional adapters:
        # - verifier (quality gates)
        # - git_ops (PR creation)

        self.console.print(f"[dim]Initialized {len(self.registry.list_adapters())} adapters[/dim]")

    def route_step(
        self, step: Dict[str, Any], policy: Optional[Dict[str, Any]] = None
    ) -> RoutingDecision:
        """Route a workflow step to the appropriate adapter."""

        actor = step.get("actor", "unknown")
        step_name = step.get("name", "Unnamed step")

        # Check if actor is available in registry
        if not self.registry.is_available(actor):
            return RoutingDecision(
                adapter_name="fallback",
                adapter_type="ai",
                reasoning=f"Actor '{actor}' not available - fallback to AI",
                estimated_tokens=500,
            )

        # Get adapter metadata
        adapter_info = self.adapters.get(actor, {})

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
                if alt_adapter and self.registry.is_available(alt_adapter):
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
            "ai_analyst": "vscode_diagnostics",  # For analysis, prefer static analysis
        }
        return alternatives.get(ai_actor)

    def get_available_actors(self) -> List[str]:
        """Get list of all available actors."""
        return self.registry.list_adapters()

    def estimate_workflow_cost(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate the total cost of executing a workflow."""
        steps = workflow.get("steps", [])
        policy = workflow.get("policy", {})

        total_tokens = 0
        deterministic_steps = 0
        ai_steps = 0

        for step in steps:
            decision = self.route_step(step, policy)

            # Use registry to get accurate cost estimate
            actor = step.get("actor", "unknown")
            if self.registry.is_available(actor):
                step_tokens = self.registry.estimate_cost(actor, step)
            else:
                step_tokens = decision.estimated_tokens

            total_tokens += step_tokens

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