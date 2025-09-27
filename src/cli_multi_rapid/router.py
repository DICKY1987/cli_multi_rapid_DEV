#!/usr/bin/env python3
"""
CLI Orchestrator Router System

Routes workflow steps between deterministic tools and AI adapters based on
configured policies and step requirements.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from rich.console import Console

from .adapters import AdapterRegistry
from .coordination import FileClaim, ScopeConflict, FileScopeManager, ScopeMode
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


@dataclass
class ParallelRoutingPlan:
    """Plan for parallel execution of multiple steps."""

    routing_decisions: List[Tuple[Dict[str, Any], RoutingDecision]]
    execution_groups: List[List[int]]  # Groups of step indices that can run in parallel
    total_estimated_cost: int = 0
    conflicts: List[ScopeConflict] = None
    resource_allocation: Dict[str, List[int]] = None  # adapter_name -> list of step indices

    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []
        if self.resource_allocation is None:
            self.resource_allocation = {}


@dataclass
class AllocationPlan:
    """Resource allocation plan for coordinated workflows."""

    assignments: Dict[str, Dict[str, Any]]  # step_id -> allocation info
    total_estimated_cost: int = 0
    estimated_usd_cost: float = 0.0
    within_budget: bool = True
    parallel_groups: List[List[str]] = None

    def __post_init__(self):
        if self.parallel_groups is None:
            self.parallel_groups = []


class Router:
    """Routes workflow steps to appropriate adapters."""

    def __init__(self):
        self.console = Console()
        self.registry = AdapterRegistry()
        self._initialize_adapters()
        self.adapters = self.registry.get_available_adapters()
        self.scope_manager = FileScopeManager()

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

        # Register Codex pipeline adapters
        from .adapters.contract_validator import ContractValidatorAdapter
        from .adapters.state_capture import StateCaptureAdapter
        from .adapters.backup_manager import BackupManagerAdapter
        from .adapters.bundle_loader import BundleLoaderAdapter
        from .adapters.enhanced_bundle_applier import EnhancedBundleApplierAdapter

        self.registry.register(ContractValidatorAdapter())
        self.registry.register(StateCaptureAdapter())
        self.registry.register(BackupManagerAdapter())
        self.registry.register(BundleLoaderAdapter())
        self.registry.register(EnhancedBundleApplierAdapter())

        # Register verification gate adapters
        from .adapters.syntax_validator import SyntaxValidatorAdapter
        from .adapters.import_resolver import ImportResolverAdapter
        from .adapters.type_checker import TypeCheckerAdapter
        from .adapters.security_scanner import SecurityScannerAdapter
        from .adapters.certificate_generator import CertificateGeneratorAdapter

        self.registry.register(SyntaxValidatorAdapter())
        self.registry.register(ImportResolverAdapter())
        self.registry.register(TypeCheckerAdapter())
        self.registry.register(SecurityScannerAdapter())
        self.registry.register(CertificateGeneratorAdapter())

        # Register verifier adapter (quality gates)
        from .adapters.verifier_adapter import VerifierAdapter

        self.registry.register(VerifierAdapter())

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

    def route_parallel_steps(self, steps: List[Dict[str, Any]],
                           policy: Optional[Dict[str, Any]] = None) -> ParallelRoutingPlan:
        """Route multiple steps to appropriate adapters with conflict detection."""

        routing_decisions = []
        file_claims = []

        # Route each step and collect file claims
        for i, step in enumerate(steps):
            decision = self.route_step(step, policy)
            routing_decisions.append((step, decision))

            # Extract file scope for conflict detection
            files = step.get('files', [])
            file_scope = step.get('file_scope', [])

            if files or file_scope:
                # Convert files to patterns for scope checking
                patterns = []
                if files:
                    patterns.extend(files if isinstance(files, list) else [files])
                if file_scope:
                    patterns.extend(file_scope if isinstance(file_scope, list) else [file_scope])

                if patterns:
                    claim = FileClaim(
                        workflow_id=f"step_{i}_{step.get('id', 'unknown')}",
                        file_patterns=patterns,
                        mode=ScopeMode(step.get('scope_mode', 'exclusive'))
                    )
                    file_claims.append(claim)

        # Detect conflicts
        conflicts = self.scope_manager.detect_conflicts(file_claims)

        # Create execution groups based on conflicts
        execution_groups = self._create_execution_groups(steps, conflicts)

        # Calculate resource allocation
        resource_allocation = self._calculate_resource_allocation(routing_decisions)

        # Calculate total cost
        total_cost = sum(decision.estimated_tokens for _, decision in routing_decisions)

        return ParallelRoutingPlan(
            routing_decisions=routing_decisions,
            execution_groups=execution_groups,
            total_estimated_cost=total_cost,
            conflicts=conflicts,
            resource_allocation=resource_allocation
        )

    def create_allocation_plan(self, workflows: List[Dict[str, Any]],
                             budget: Optional[float] = None,
                             max_parallel: int = 3) -> AllocationPlan:
        """Create resource allocation plan for coordinated workflows."""

        adapter_assignments = {}
        cost_estimates = {}
        total_cost = 0

        for workflow in workflows:
            workflow_name = workflow.get('name', 'unnamed_workflow')

            # Process phases or steps
            phases = workflow.get('phases', [])
            steps = workflow.get('steps', [])

            # Handle phases (IPT-WT pattern)
            if phases:
                for phase in phases:
                    phase_id = phase.get('id', 'unknown_phase')
                    tasks = phase.get('tasks', [])

                    for task in tasks:
                        task_id = f"{workflow_name}_{phase_id}_{task}" if isinstance(task, str) else f"{workflow_name}_{phase_id}_{task.get('id', 'unknown')}"

                        # Convert task to step format for routing
                        if isinstance(task, str):
                            step = {"id": task, "actor": "unknown", "name": task}
                        else:
                            step = task

                        # Route to appropriate adapter
                        adapter_decision = self.route_step(step)
                        cost = adapter_decision.estimated_tokens

                        adapter_assignments[task_id] = {
                            'adapter': adapter_decision.adapter_name,
                            'adapter_type': adapter_decision.adapter_type,
                            'estimated_cost': cost,
                            'priority': phase.get('priority', 1),
                            'workflow': workflow_name,
                            'phase': phase_id
                        }
                        total_cost += cost

            # Handle direct steps (traditional workflow)
            elif steps:
                for step in steps:
                    step_id = f"{workflow_name}_{step.get('id', 'unknown_step')}"

                    adapter_decision = self.route_step(step)
                    cost = adapter_decision.estimated_tokens

                    adapter_assignments[step_id] = {
                        'adapter': adapter_decision.adapter_name,
                        'adapter_type': adapter_decision.adapter_type,
                        'estimated_cost': cost,
                        'priority': step.get('priority', 1),
                        'workflow': workflow_name
                    }
                    total_cost += cost

        # Calculate parallel groups
        parallel_groups = self._create_workflow_parallel_groups(workflows)

        # Check budget constraints
        estimated_usd_cost = total_cost * 0.0005  # Rough estimate: $0.50 per 1000 tokens
        within_budget = budget is None or estimated_usd_cost <= budget

        return AllocationPlan(
            assignments=adapter_assignments,
            total_estimated_cost=total_cost,
            estimated_usd_cost=estimated_usd_cost,
            within_budget=within_budget,
            parallel_groups=parallel_groups
        )

    def estimate_parallel_cost(self, steps: List[Dict[str, Any]]) -> int:
        """Estimate cost for parallel step execution."""

        total_cost = 0
        for step in steps:
            decision = self.route_step(step)
            total_cost += decision.estimated_tokens

        return total_cost

    def get_adapter_availability(self) -> Dict[str, bool]:
        """Get availability status of all adapters."""

        availability = {}
        for adapter_name in self.adapters.keys():
            availability[adapter_name] = self.registry.is_available(adapter_name)

        return availability

    def _create_execution_groups(self, steps: List[Dict[str, Any]],
                               conflicts: List[ScopeConflict]) -> List[List[int]]:
        """Create groups of step indices that can run in parallel."""

        groups = []

        if not conflicts:
            # No conflicts, all steps can potentially run in parallel
            # Group by adapter type to avoid resource contention
            deterministic_steps = []
            ai_steps = []

            for i, step in enumerate(steps):
                decision = self.route_step(step)
                if decision.adapter_type == "deterministic":
                    deterministic_steps.append(i)
                else:
                    ai_steps.append(i)

            if deterministic_steps:
                groups.append(deterministic_steps)
            if ai_steps:
                # Limit AI steps to avoid overwhelming AI services
                while ai_steps:
                    batch = ai_steps[:3]  # Max 3 AI steps in parallel
                    groups.append(batch)
                    ai_steps = ai_steps[3:]
        else:
            # Create groups avoiding conflicts
            conflicting_step_ids = set()
            for conflict in conflicts:
                for workflow_id in conflict.workflow_ids:
                    # Extract step index from workflow_id (format: step_{i}_{step_id})
                    if workflow_id.startswith("step_"):
                        try:
                            step_index = int(workflow_id.split("_")[1])
                            conflicting_step_ids.add(step_index)
                        except (IndexError, ValueError):
                            pass

            # Group non-conflicting steps together
            non_conflicting = []
            for i in range(len(steps)):
                if i not in conflicting_step_ids:
                    non_conflicting.append(i)

            if non_conflicting:
                groups.append(non_conflicting)

            # Add conflicting steps as individual groups
            for step_id in conflicting_step_ids:
                groups.append([step_id])

        return groups

    def _calculate_resource_allocation(self, routing_decisions: List[Tuple[Dict[str, Any], RoutingDecision]]) -> Dict[str, List[int]]:
        """Calculate which steps will use which adapters."""

        allocation = {}

        for i, (step, decision) in enumerate(routing_decisions):
            adapter_name = decision.adapter_name
            if adapter_name not in allocation:
                allocation[adapter_name] = []
            allocation[adapter_name].append(i)

        return allocation

    def _create_workflow_parallel_groups(self, workflows: List[Dict[str, Any]]) -> List[List[str]]:
        """Create parallel groups for multiple workflows."""

        # Simple implementation: group workflows by priority
        priority_groups = {}

        for workflow in workflows:
            workflow_name = workflow.get('name', 'unnamed_workflow')
            priority = workflow.get('metadata', {}).get('coordination', {}).get('priority', 1)

            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(workflow_name)

        # Convert to list of groups, ordered by priority (highest first)
        groups = []
        for priority in sorted(priority_groups.keys(), reverse=True):
            groups.append(priority_groups[priority])

        return groups
