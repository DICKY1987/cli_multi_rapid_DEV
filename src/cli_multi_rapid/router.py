#!/usr/bin/env python3
"""
CLI Orchestrator Router System

Routes workflow steps between deterministic tools and AI adapters based on
configured policies, step requirements, and intelligent optimization.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from rich.console import Console

from .adapters import AdapterRegistry
from .adapters.ai_analyst import AIAnalystAdapter
from .adapters.ai_editor import AIEditorAdapter
from .adapters.code_fixers import CodeFixersAdapter
from .adapters.pytest_runner import PytestRunnerAdapter
from .adapters.vscode_diagnostics import VSCodeDiagnosticsAdapter
from .lib.error_recovery import IntelligentErrorRecovery
from .lib.optimizer import PredictiveOptimizer

console = Console()
logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern for adapter failure handling."""

    def __init__(
        self, failures: int = 3, window_sec: int = 300, cooldown_sec: int = 120
    ):
        self.failures = failures
        self.window_sec = window_sec
        self.cooldown_sec = cooldown_sec
        self._events = []  # List of (timestamp, success) tuples
        self._open_until = 0

    def record(self, ok: bool, now: int) -> None:
        """Record adapter execution result."""
        # Clean old events outside window
        self._events = [e for e in self._events if now - e[0] <= self.window_sec]
        self._events.append((now, ok))

        # Check if we should open the circuit
        if not ok:
            failures = sum(1 for _, success in self._events if not success)
            if failures >= self.failures:
                from time import time as _t

                self._open_until = int(_t()) + self.cooldown_sec

    def allow(self, now: int) -> bool:
        """Check if adapter execution is allowed."""
        from time import time as _t

        return _t() >= self._open_until


class BudgetGuard:
    """Budget enforcement for AI adapter routing."""

    def __init__(self, cost_tracker):
        self.cost = cost_tracker

    def allow_ai(self, step_budget: Optional[float]) -> bool:
        """Check if AI adapter usage is within budget."""
        remaining = max(0.0, step_budget if step_budget is not None else 1e9)

        # Simple gate: require at least 20% of step budget remaining
        if hasattr(self.cost, "remaining_usd"):
            return self.cost.remaining_usd() >= (0.2 * remaining)

        return True  # Allow if cost tracker not available


@dataclass
class RoutingDecision:
    """Result of routing decision for a workflow step."""

    adapter_name: str
    adapter_type: str  # "deterministic" or "ai"
    reasoning: str
    estimated_tokens: int = 0
    confidence: float = 1.0
    alternatives: list[str] = None
    optimization_applied: bool = False

    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


class Router:
    """Routes workflow steps to appropriate adapters with intelligent optimization."""

    def __init__(self, enable_optimization: bool = True):
        self.console = Console()
        self.registry = AdapterRegistry()
        self._initialize_adapters()
        self.adapters = self.registry.get_available_adapters()

        # Initialize intelligent components
        self.enable_optimization = enable_optimization
        self.optimizer = PredictiveOptimizer() if enable_optimization else None
        self.error_recovery = IntelligentErrorRecovery()
        self.routing_history: list[dict[str, Any]] = []

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
        self,
        step: dict[str, Any],
        policy: Optional[dict[str, Any]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> RoutingDecision:
        """Route a workflow step to the appropriate adapter with intelligent optimization."""

        actor = step.get("actor", "unknown")
        step.get("name", "Unnamed step")
        context = context or {}

        # Apply intelligent optimization if enabled
        if self.enable_optimization and self.optimizer:
            optimized_decision = self._get_optimized_routing(step, policy, context)
            if optimized_decision:
                return optimized_decision

        # Check if actor is available in registry
        if not self.registry.is_available(actor):
            # Try to find intelligent alternative
            alternative = self._find_intelligent_alternative(actor, step, context)
            if alternative:
                return RoutingDecision(
                    adapter_name=alternative,
                    adapter_type=self._get_adapter_type(alternative),
                    reasoning=f"Actor '{actor}' not available - intelligent alternative: {alternative}",
                    estimated_tokens=self._estimate_tokens(alternative, step),
                    confidence=0.8,
                    alternatives=[actor],
                )

            return RoutingDecision(
                adapter_name="fallback",
                adapter_type="ai",
                reasoning=f"Actor '{actor}' not available - fallback to AI",
                estimated_tokens=500,
                confidence=0.3,
            )

        # Get adapter metadata
        adapter_info = self.adapters.get(actor, {})

        # Apply routing policy with intelligent enhancements
        prefer_deterministic = True
        if policy:
            prefer_deterministic = policy.get("prefer_deterministic", True)

        # Enhanced routing based on adapter type, policy, and context
        decision = self._make_routing_decision(
            actor, adapter_info, prefer_deterministic, step, context
        )

        # Record routing decision for learning
        self._record_routing_decision(step, decision, context)

        return decision

    def _get_optimized_routing(
        self,
        step: dict[str, Any],
        policy: Optional[dict[str, Any]],
        context: dict[str, Any],
    ) -> Optional[RoutingDecision]:
        """Get optimized routing decision using predictive optimizer."""
        try:
            task_description = self._extract_task_description(step)
            budget_limit = policy.get("max_tokens") if policy else None
            priority = context.get("priority", "balanced")

            recommendation = self.optimizer.recommend_tool_for_task(
                task_description, budget_limit=budget_limit, priority=priority
            )

            if recommendation.confidence > 0.7:
                recommended_tool = recommendation.recommended_tool

                # Map optimizer tool names to adapter names
                adapter_name = self._map_tool_to_adapter(recommended_tool)

                if adapter_name and self.registry.is_available(adapter_name):
                    return RoutingDecision(
                        adapter_name=adapter_name,
                        adapter_type=self._get_adapter_type(adapter_name),
                        reasoning=f"Optimized selection: {recommendation.reasoning}",
                        estimated_tokens=int(recommendation.predicted_cost),
                        confidence=recommendation.confidence,
                        alternatives=[
                            alt[0] for alt in recommendation.alternatives[:3]
                        ],
                        optimization_applied=True,
                    )

        except Exception as e:
            logger.warning(f"Optimization routing failed: {e}")

        return None

    def _find_intelligent_alternative(
        self, unavailable_actor: str, step: dict[str, Any], context: dict[str, Any]
    ) -> Optional[str]:
        """Find intelligent alternative for unavailable actor."""

        # First try deterministic alternative
        deterministic_alt = self._find_deterministic_alternative(unavailable_actor)
        if deterministic_alt and self.registry.is_available(deterministic_alt):
            return deterministic_alt

        # Try capability-based matching
        task_description = self._extract_task_description(step)
        suitable_adapters = self._find_adapters_by_capability(task_description)

        for adapter_name in suitable_adapters:
            if self.registry.is_available(adapter_name):
                return adapter_name

        # Try semantic similarity
        semantic_alt = self._find_semantic_alternative(unavailable_actor)
        if semantic_alt and self.registry.is_available(semantic_alt):
            return semantic_alt

        return None

    def _make_routing_decision(
        self,
        actor: str,
        adapter_info: dict[str, Any],
        prefer_deterministic: bool,
        step: dict[str, Any],
        context: dict[str, Any],
    ) -> RoutingDecision:
        """Make enhanced routing decision with context awareness."""

        adapter_type = adapter_info.get("type", "unknown")

        # Route based on adapter type and policy
        if adapter_type == "deterministic":
            # Check if deterministic tool is likely to succeed
            success_probability = self._estimate_success_probability(
                actor, step, context
            )

            return RoutingDecision(
                adapter_name=actor,
                adapter_type="deterministic",
                reasoning=f"Deterministic tool: {adapter_info.get('description', 'No description')}",
                estimated_tokens=0,
                confidence=success_probability,
                alternatives=self._get_alternatives(actor),
            )

        elif adapter_type == "ai":
            if prefer_deterministic:
                # Enhanced deterministic alternative search
                alt_adapter = self._find_enhanced_deterministic_alternative(
                    actor, step, context
                )
                if alt_adapter and self.registry.is_available(alt_adapter):
                    return RoutingDecision(
                        adapter_name=alt_adapter,
                        adapter_type="deterministic",
                        reasoning=f"Policy prefers deterministic - using {alt_adapter} instead of {actor}",
                        estimated_tokens=0,
                        confidence=0.8,
                        alternatives=[actor],
                    )

            # Use AI adapter with enhanced estimation
            estimated_cost = self._estimate_ai_cost(actor, step, context)
            success_probability = self._estimate_success_probability(
                actor, step, context
            )

            return RoutingDecision(
                adapter_name=actor,
                adapter_type="ai",
                reasoning=f"AI tool: {adapter_info.get('description', 'No description')}",
                estimated_tokens=estimated_cost,
                confidence=success_probability,
                alternatives=self._get_alternatives(actor),
            )

        # Fallback with context
        return RoutingDecision(
            adapter_name="fallback",
            adapter_type="ai",
            reasoning="Fallback routing due to configuration error",
            estimated_tokens=500,
            confidence=0.2,
        )

    def _extract_task_description(self, step: dict[str, Any]) -> str:
        """Extract task description from step for optimization."""
        parts = []

        if step.get("name"):
            parts.append(step["name"])

        if step.get("with", {}).get("goal"):
            parts.append(step["with"]["goal"])

        if step.get("task"):
            parts.append(step["task"])

        return " ".join(parts) if parts else "Generic task"

    def _map_tool_to_adapter(self, tool_name: str) -> Optional[str]:
        """Map optimizer tool names to actual adapter names."""
        mapping = {
            "python_tools": "vscode_diagnostics",
            "javascript_tools": "vscode_diagnostics",
            "testing_tools": "pytest_runner",
            "documentation_tools": "ai_editor",
            "git_ops": "git_ops",
            "general_tools": "code_fixers",
            "aider": "ai_editor",
            "claude-cli": "ai_analyst",
            "cursor": "ai_editor",
        }
        return mapping.get(tool_name)

    def _get_adapter_type(self, adapter_name: str) -> str:
        """Get adapter type for given adapter name."""
        adapter_info = self.adapters.get(adapter_name, {})
        return adapter_info.get("type", "unknown")

    def _estimate_tokens(self, adapter_name: str, step: dict[str, Any]) -> int:
        """Estimate token usage for adapter and step."""
        adapter_info = self.adapters.get(adapter_name, {})
        base_cost = adapter_info.get("cost", 500)

        # Adjust based on step complexity
        complexity_factor = self._estimate_step_complexity(step)
        return int(base_cost * complexity_factor)

    def _estimate_step_complexity(self, step: dict[str, Any]) -> float:
        """Estimate step complexity factor (1.0 = baseline)."""
        task_desc = self._extract_task_description(step)

        # Simple heuristics for complexity
        if any(word in task_desc.lower() for word in ["simple", "quick", "basic"]):
            return 0.5
        elif any(
            word in task_desc.lower()
            for word in ["complex", "advanced", "comprehensive"]
        ):
            return 2.0
        elif any(
            word in task_desc.lower() for word in ["implement", "create", "build"]
        ):
            return 1.5

        return 1.0

    def _find_adapters_by_capability(self, task_description: str) -> list[str]:
        """Find adapters suitable for a task based on capabilities."""
        task_lower = task_description.lower()
        suitable_adapters = []

        capability_map = {
            "test": ["pytest_runner"],
            "python": ["vscode_diagnostics", "code_fixers"],
            "javascript": ["vscode_diagnostics"],
            "git": ["git_ops"],
            "analysis": ["vscode_diagnostics", "ai_analyst"],
            "edit": ["ai_editor", "code_fixers"],
            "github": ["github_integration"],
        }

        for capability, adapters in capability_map.items():
            if capability in task_lower:
                suitable_adapters.extend(adapters)

        return list(set(suitable_adapters))  # Remove duplicates

    def _find_semantic_alternative(self, actor: str) -> Optional[str]:
        """Find semantically similar adapter."""
        semantic_groups = {
            "editors": ["ai_editor", "code_fixers"],
            "analyzers": ["ai_analyst", "vscode_diagnostics"],
            "testers": ["pytest_runner"],
            "version_control": ["git_ops", "github_integration"],
        }

        for _group_name, adapters in semantic_groups.items():
            if actor in adapters:
                # Return first available alternative in the group
                for alt in adapters:
                    if alt != actor and self.registry.is_available(alt):
                        return alt

        return None

    def _find_enhanced_deterministic_alternative(
        self, ai_actor: str, step: dict[str, Any], context: dict[str, Any]
    ) -> Optional[str]:
        """Enhanced deterministic alternative finder with context."""

        # Base deterministic alternatives
        base_alt = self._find_deterministic_alternative(ai_actor)
        if base_alt:
            return base_alt

        # Context-aware alternatives
        task_desc = self._extract_task_description(step)

        if "test" in task_desc.lower():
            return "pytest_runner"
        elif any(word in task_desc.lower() for word in ["format", "lint", "fix"]):
            return "code_fixers"
        elif "diagnostic" in task_desc.lower():
            return "vscode_diagnostics"

        return None

    def _estimate_success_probability(
        self, adapter_name: str, step: dict[str, Any], context: dict[str, Any]
    ) -> float:
        """Estimate probability of adapter success for given step."""

        # Use historical data if available
        if self.optimizer:
            try:
                task_desc = self._extract_task_description(step)
                recommendation = self.optimizer.recommend_tool_for_task(task_desc)
                mapped_adapter = self._map_tool_to_adapter(
                    recommendation.recommended_tool
                )

                if mapped_adapter == adapter_name:
                    return recommendation.success_probability

            except Exception:
                pass

        # Fallback to heuristics
        adapter_info = self.adapters.get(adapter_name, {})
        base_reliability = adapter_info.get("reliability", 0.8)

        # Adjust based on step-adapter compatibility
        task_desc = self._extract_task_description(step)
        compatibility = self._calculate_compatibility(adapter_name, task_desc)

        return min(1.0, base_reliability * compatibility)

    def _calculate_compatibility(
        self, adapter_name: str, task_description: str
    ) -> float:
        """Calculate compatibility between adapter and task."""
        task_lower = task_description.lower()

        compatibility_rules = {
            "pytest_runner": ["test", "pytest", "unittest", "spec"],
            "code_fixers": ["format", "lint", "fix", "cleanup"],
            "vscode_diagnostics": ["analyze", "diagnostic", "check", "validate"],
            "ai_editor": ["implement", "create", "edit", "modify"],
            "ai_analyst": ["analyze", "review", "assess", "evaluate"],
            "git_ops": ["git", "commit", "branch", "merge"],
            "github_integration": ["github", "issue", "pr", "release"],
        }

        keywords = compatibility_rules.get(adapter_name, [])
        matches = sum(1 for keyword in keywords if keyword in task_lower)

        if not keywords:
            return 0.5  # Neutral compatibility

        return min(1.0, 0.3 + (matches / len(keywords)) * 0.7)

    def _estimate_ai_cost(
        self, adapter_name: str, step: dict[str, Any], context: dict[str, Any]
    ) -> int:
        """Enhanced AI cost estimation."""
        base_cost = self.adapters.get(adapter_name, {}).get("cost", 1000)
        complexity_factor = self._estimate_step_complexity(step)

        # Adjust for context
        if context.get("priority") == "speed":
            complexity_factor *= 0.8  # Faster, potentially less thorough
        elif context.get("priority") == "quality":
            complexity_factor *= 1.3  # More thorough, higher cost

        return int(base_cost * complexity_factor)

    def _get_alternatives(self, adapter_name: str) -> list[str]:
        """Get alternative adapters for given adapter."""
        alternatives = []

        # Add deterministic alternative if this is AI
        adapter_info = self.adapters.get(adapter_name, {})
        if adapter_info.get("type") == "ai":
            det_alt = self._find_deterministic_alternative(adapter_name)
            if det_alt:
                alternatives.append(det_alt)

        # Add semantic alternatives
        semantic_alt = self._find_semantic_alternative(adapter_name)
        if semantic_alt:
            alternatives.append(semantic_alt)

        return alternatives

    def _record_routing_decision(
        self, step: dict[str, Any], decision: RoutingDecision, context: dict[str, Any]
    ):
        """Record routing decision for learning and improvement."""
        record = {
            "timestamp": context.get("timestamp", "unknown"),
            "step_id": step.get("id", "unknown"),
            "step_name": step.get("name", "unknown"),
            "requested_actor": step.get("actor", "unknown"),
            "selected_adapter": decision.adapter_name,
            "adapter_type": decision.adapter_type,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "estimated_tokens": decision.estimated_tokens,
            "optimization_applied": decision.optimization_applied,
            "context": context,
        }

        self.routing_history.append(record)

        # Keep only recent history to prevent memory bloat
        if len(self.routing_history) > 1000:
            self.routing_history = self.routing_history[-500:]

    def get_routing_statistics(self) -> dict[str, Any]:
        """Get routing statistics and insights."""
        if not self.routing_history:
            return {"total_decisions": 0}

        total_decisions = len(self.routing_history)
        adapter_usage = {}
        optimization_rate = 0
        avg_confidence = 0

        for record in self.routing_history:
            adapter = record["selected_adapter"]
            adapter_usage[adapter] = adapter_usage.get(adapter, 0) + 1

            if record["optimization_applied"]:
                optimization_rate += 1

            avg_confidence += record["confidence"]

        optimization_rate = optimization_rate / total_decisions
        avg_confidence = avg_confidence / total_decisions

        return {
            "total_decisions": total_decisions,
            "adapter_usage": adapter_usage,
            "optimization_rate": optimization_rate,
            "average_confidence": avg_confidence,
            "most_used_adapter": (
                max(adapter_usage.items(), key=lambda x: x[1])[0]
                if adapter_usage
                else None
            ),
        }

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
