#!/usr/bin/env python3
"""
CLI Orchestrator Router System

Routes workflow steps between deterministic tools and AI adapters based on
configured policies and step requirements.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, List

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
        from .adapters.git_ops import GitOpsAdapter

        self.registry.register(GitOpsAdapter())
        from .adapters.github_integration import GitHubIntegrationAdapter

        self.registry.register(GitHubIntegrationAdapter())

        # Register tool adapter bridges
        from .adapters.tool_adapter_bridge import ToolAdapterBridge

        self.registry.register(ToolAdapterBridge("vcs"))
        self.registry.register(ToolAdapterBridge("containers"))
        self.registry.register(ToolAdapterBridge("editor"))
        self.registry.register(ToolAdapterBridge("js_runtime"))
        self.registry.register(ToolAdapterBridge("ai_cli"))
        self.registry.register(ToolAdapterBridge("python_quality"))
        self.registry.register(ToolAdapterBridge("precommit"))

        # Register AI-powered adapters
        self.registry.register(AIEditorAdapter())
        self.registry.register(AIAnalystAdapter())

        # TODO: Register additional adapters:
        # - verifier (quality gates)

        self.console.print(
            f"[dim]Initialized {len(self.registry.list_adapters())} adapters[/dim]"
        )

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
        """Suggest a deterministic alternative for a given AI actor, if any.

        This provides a conservative mapping to help uphold a determinism-first
        policy. If no sensible alternative exists, returns None.
        """
        mapping = {
            # Prefer quick, cheap diagnostics/fixes when possible
            "ai_editor": "code_fixers",
            "ai_analyst": "vscode_diagnostics",
        }
        return mapping.get(ai_actor)

    def route_with_budget_awareness(
        self,
        step: Dict[str, Any],
        role: str,
        budget_remaining: Optional[int] = None,
    ) -> RoutingDecision:
        """Route a step considering a budget and role preferences.

        - role: 'ipt' or 'wt' (case-insensitive)
        - budget_remaining: if None, falls back to route_step
        """
        try:
            if budget_remaining is None:
                return self.route_step(step)

            role_lc = (role or "").lower()
            if role_lc == "ipt":
                preferred: List[str] = ["ai_analyst", "ai_editor"]
            else:  # default to WT
                preferred = ["code_fixers", "pytest_runner", "vscode_diagnostics"]

            # Try preferred in order within budget
            for name in preferred:
                if not self.registry.is_available(name):
                    continue
                est = self.registry.estimate_cost(name, step)
                if est <= (budget_remaining or 0):
                    adapter = self.registry.get_adapter(name)
                    a_type = getattr(adapter, "adapter_type", None)
                    a_type_str = getattr(a_type, "value", "deterministic") if a_type else "deterministic"
                    return RoutingDecision(
                        adapter_name=name,
                        adapter_type=a_type_str,
                        reasoning=f"Selected {name} for role={role_lc} within budget",
                        estimated_tokens=est,
                    )

            # If none fit budget, choose cheapest available deterministic as fallback
            cheapest_name = None
            cheapest_cost = None
            for name, meta in self.adapters.items():
                if meta.get("type") == "deterministic" and self.registry.is_available(name):
                    est = self.registry.estimate_cost(name, step)
                    if cheapest_cost is None or est < cheapest_cost:
                        cheapest_name = name
                        cheapest_cost = est

            if cheapest_name:
                return RoutingDecision(
                    adapter_name=cheapest_name,
                    adapter_type="deterministic",
                    reasoning=f"Budget exceeded; using cheapest deterministic: {cheapest_name}",
                    estimated_tokens=cheapest_cost or 0,
                )

            # Final fallback: original policy routing
            return self.route_step(step)
        except Exception as e:
            return RoutingDecision(
                adapter_name="fallback",
                adapter_type="ai",
                reasoning=f"Budget-aware routing failed: {e}",
                estimated_tokens=0,
            )
