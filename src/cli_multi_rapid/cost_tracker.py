#!/usr/bin/env python3
"""
CLI Orchestrator Cost Tracker

Tracks token usage, estimates costs, and enforces budget limits for
workflow executions that involve AI services.
"""

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
from collections import defaultdict

from rich.console import Console

console = Console()


@dataclass
class TokenUsage:
    """Records token usage for a single operation."""

    timestamp: str
    operation: str
    tokens_used: int
    estimated_cost: float
    model: str = "unknown"
    success: bool = True
    workflow_id: Optional[str] = None
    coordination_id: Optional[str] = None
    phase_id: Optional[str] = None
    adapter_name: Optional[str] = None


@dataclass
class BudgetLimit:
    """Budget enforcement configuration."""

    daily_token_limit: int = 100000
    daily_cost_limit: float = 10.0
    per_workflow_limit: int = 50000
    warn_threshold: float = 0.8


@dataclass
class CoordinationBudget:
    """Budget configuration for coordinated workflows."""

    total_budget: float = 25.0
    per_workflow_budget: float = 10.0
    emergency_reserve: float = 5.0
    workflow_allocations: Dict[str, float] = None
    priority_multipliers: Dict[int, float] = None

    def __post_init__(self):
        if self.workflow_allocations is None:
            self.workflow_allocations = {}
        if self.priority_multipliers is None:
            # Higher priority workflows get more budget
            self.priority_multipliers = {
                1: 0.5,   # Low priority
                2: 1.0,   # Normal priority
                3: 1.5,   # High priority
                4: 2.0,   # Critical priority
                5: 3.0    # Emergency priority
            }


@dataclass
class WorkflowCostSummary:
    """Summary of costs for a workflow."""

    workflow_id: str
    total_tokens: int = 0
    total_cost: float = 0.0
    operations_count: int = 0
    success_rate: float = 0.0
    budget_allocated: float = 0.0
    budget_used: float = 0.0
    budget_remaining: float = 0.0
    phases: Dict[str, Dict[str, Any]] = None

    def __post_init__(self):
        if self.phases is None:
            self.phases = {}
        self.budget_remaining = self.budget_allocated - self.budget_used


class CostTracker:
    """Tracks and manages AI token usage and costs."""

    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        self.usage_file = self.logs_dir / "token_usage.jsonl"
        self.console = Console()

    def record_usage(
        self,
        operation: str,
        tokens_used: int,
        model: str = "unknown",
        success: bool = True,
        workflow_id: Optional[str] = None,
        coordination_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        adapter_name: Optional[str] = None,
    ) -> float:
        """Record token usage and return estimated cost."""

        # Estimate cost based on model (rough estimates)
        cost_per_token = self._get_cost_per_token(model)
        estimated_cost = tokens_used * cost_per_token

        usage = TokenUsage(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            tokens_used=tokens_used,
            estimated_cost=estimated_cost,
            model=model,
            success=success,
            workflow_id=workflow_id,
            coordination_id=coordination_id,
            phase_id=phase_id,
            adapter_name=adapter_name,
        )

        # Write to JSONL log file
        try:
            with open(self.usage_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(usage)) + "\n")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not log usage - {e}[/yellow]")

        return estimated_cost

    def _get_cost_per_token(self, model: str) -> float:
        """Get estimated cost per token for different models."""
        # Rough estimates - actual costs vary by provider and model
        costs = {
            "gpt-4": 0.00006,
            "gpt-3.5-turbo": 0.000002,
            "claude-3": 0.00008,
            "claude-instant": 0.00024,
            "unknown": 0.00001,  # Conservative fallback
        }
        return costs.get(model.lower(), costs["unknown"])

    def get_daily_usage(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Get token usage summary for a specific date."""
        if target_date is None:
            target_date = date.today()

        target_date_str = target_date.isoformat()

        daily_tokens = 0
        daily_cost = 0.0
        operations = []

        try:
            if self.usage_file.exists():
                with open(self.usage_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            usage = json.loads(line.strip())
                            usage_date = usage["timestamp"][:10]  # Extract YYYY-MM-DD

                            if usage_date == target_date_str:
                                daily_tokens += usage["tokens_used"]
                                daily_cost += usage["estimated_cost"]
                                operations.append(usage)

        except Exception as e:
            console.print(f"[yellow]Warning: Could not read usage log - {e}[/yellow]")

        return {
            "date": target_date_str,
            "total_tokens": daily_tokens,
            "total_cost": daily_cost,
            "operations": operations,
            "operation_count": len(operations),
        }

    def check_budget_limits(
        self, budget: Optional[BudgetLimit] = None, tokens_to_spend: int = 0
    ) -> Dict[str, Any]:
        """Check if operation would exceed budget limits."""

        if budget is None:
            budget = BudgetLimit()

        daily_usage = self.get_daily_usage()

        current_tokens = daily_usage["total_tokens"]
        current_cost = daily_usage["total_cost"]

        projected_tokens = current_tokens + tokens_to_spend
        projected_cost = current_cost + (tokens_to_spend * 0.00001)  # Rough estimate

        return {
            "within_daily_token_limit": projected_tokens <= budget.daily_token_limit,
            "within_daily_cost_limit": projected_cost <= budget.daily_cost_limit,
            "within_workflow_limit": tokens_to_spend <= budget.per_workflow_limit,
            "current_tokens": current_tokens,
            "current_cost": current_cost,
            "projected_tokens": projected_tokens,
            "projected_cost": projected_cost,
            "daily_token_limit": budget.daily_token_limit,
            "daily_cost_limit": budget.daily_cost_limit,
            "workflow_limit": budget.per_workflow_limit,
            "warn_if_over": projected_cost
            >= (budget.daily_cost_limit * budget.warn_threshold),
        }

    def generate_report(
        self, last_run: bool = False, detailed: bool = False, days: int = 7
    ) -> Dict[str, Any]:
        """Generate usage and cost report."""

        if last_run:
            # Get most recent operation
            operations = []
            try:
                if self.usage_file.exists():
                    with open(self.usage_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                operations.append(json.loads(line.strip()))

                if operations:
                    last_op = operations[-1]
                    return {
                        "period": "last_run",
                        "operation": last_op["operation"],
                        "tokens": last_op["tokens_used"],
                        "cost": last_op["estimated_cost"],
                        "timestamp": last_op["timestamp"],
                        "success": last_op["success"],
                    }
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not read usage log - {e}[/yellow]"
                )

            return {"period": "last_run", "error": "No operations found"}

        # Multi-day summary
        total_tokens = 0
        total_cost = 0.0
        runs_today = 0

        today_usage = self.get_daily_usage()
        total_tokens = today_usage["total_tokens"]
        total_cost = today_usage["total_cost"]
        runs_today = today_usage["operation_count"]

        report = {
            "period": f"last_{days}_days",
            "total_tokens": total_tokens,
            "estimated_cost": total_cost,
            "runs_today": runs_today,
            "average_cost_per_run": total_cost / max(runs_today, 1),
        }

        if detailed:
            report["daily_breakdown"] = today_usage

        return report

    def track_coordinated_cost(self, coordination_id: str, workflow_id: str,
                             operation: str, tokens_used: int, model: str = "unknown",
                             phase_id: Optional[str] = None, adapter_name: Optional[str] = None) -> float:
        """Track cost for coordinated workflow execution."""

        return self.record_usage(
            operation=operation,
            tokens_used=tokens_used,
            model=model,
            workflow_id=workflow_id,
            coordination_id=coordination_id,
            phase_id=phase_id,
            adapter_name=adapter_name
        )

    def allocate_budget(self, workflows: List[Dict[str, Any]],
                       coordination_budget: CoordinationBudget) -> Dict[str, float]:
        """Allocate budget across workflows based on priority and requirements."""

        allocations = {}
        total_workflows = len(workflows)
        remaining_budget = coordination_budget.total_budget - coordination_budget.emergency_reserve

        # Calculate priority scores for each workflow
        workflow_priorities = {}
        total_priority_score = 0

        for workflow in workflows:
            workflow_id = workflow.get('name', 'unnamed_workflow')
            priority = workflow.get('metadata', {}).get('coordination', {}).get('priority', 2)
            priority_multiplier = coordination_budget.priority_multipliers.get(priority, 1.0)

            # Estimate complexity factor based on workflow structure
            complexity_factor = self._estimate_workflow_complexity(workflow)

            priority_score = priority_multiplier * complexity_factor
            workflow_priorities[workflow_id] = priority_score
            total_priority_score += priority_score

        # Allocate budget proportionally based on priority scores
        for workflow_id, priority_score in workflow_priorities.items():
            if total_priority_score > 0:
                proportion = priority_score / total_priority_score
                allocated_budget = min(
                    remaining_budget * proportion,
                    coordination_budget.per_workflow_budget
                )
            else:
                allocated_budget = remaining_budget / total_workflows

            allocations[workflow_id] = allocated_budget

        return allocations

    def get_coordination_summary(self, coordination_id: str) -> Dict[str, Any]:
        """Get cost summary for a coordination session."""

        workflows = defaultdict(lambda: {
            'total_tokens': 0,
            'total_cost': 0.0,
            'operations': [],
            'phases': defaultdict(lambda: {'tokens': 0, 'cost': 0.0, 'operations': 0})
        })

        total_cost = 0.0
        total_tokens = 0
        total_operations = 0

        try:
            if self.usage_file.exists():
                with open(self.usage_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            usage = json.loads(line.strip())

                            if usage.get('coordination_id') == coordination_id:
                                workflow_id = usage.get('workflow_id', 'unknown')
                                phase_id = usage.get('phase_id')

                                workflows[workflow_id]['total_tokens'] += usage['tokens_used']
                                workflows[workflow_id]['total_cost'] += usage['estimated_cost']
                                workflows[workflow_id]['operations'].append(usage)

                                if phase_id:
                                    workflows[workflow_id]['phases'][phase_id]['tokens'] += usage['tokens_used']
                                    workflows[workflow_id]['phases'][phase_id]['cost'] += usage['estimated_cost']
                                    workflows[workflow_id]['phases'][phase_id]['operations'] += 1

                                total_cost += usage['estimated_cost']
                                total_tokens += usage['tokens_used']
                                total_operations += 1

        except Exception as e:
            console.print(f"[yellow]Warning: Could not read coordination usage - {e}[/yellow]")

        # Convert defaultdicts to regular dicts for JSON serialization
        workflows_dict = {}
        for workflow_id, workflow_data in workflows.items():
            workflows_dict[workflow_id] = {
                'total_tokens': workflow_data['total_tokens'],
                'total_cost': workflow_data['total_cost'],
                'operations_count': len(workflow_data['operations']),
                'phases': dict(workflow_data['phases'])
            }

        return {
            'coordination_id': coordination_id,
            'total_cost': total_cost,
            'total_tokens': total_tokens,
            'total_operations': total_operations,
            'workflows': workflows_dict,
            'average_cost_per_workflow': total_cost / max(len(workflows), 1),
            'timestamp': datetime.now().isoformat()
        }

    def get_workflow_cost_summary(self, workflow_id: str,
                                coordination_id: Optional[str] = None) -> WorkflowCostSummary:
        """Get detailed cost summary for a specific workflow."""

        summary = WorkflowCostSummary(workflow_id=workflow_id)

        try:
            if self.usage_file.exists():
                with open(self.usage_file, "r", encoding="utf-8") as f:
                    successful_ops = 0
                    total_ops = 0

                    for line in f:
                        if line.strip():
                            usage = json.loads(line.strip())

                            # Filter by workflow_id and optionally coordination_id
                            if (usage.get('workflow_id') == workflow_id and
                                (coordination_id is None or usage.get('coordination_id') == coordination_id)):

                                summary.total_tokens += usage['tokens_used']
                                summary.total_cost += usage['estimated_cost']
                                total_ops += 1

                                if usage.get('success', True):
                                    successful_ops += 1

                                # Track phase-level costs
                                phase_id = usage.get('phase_id')
                                if phase_id:
                                    if phase_id not in summary.phases:
                                        summary.phases[phase_id] = {
                                            'tokens': 0,
                                            'cost': 0.0,
                                            'operations': 0
                                        }
                                    summary.phases[phase_id]['tokens'] += usage['tokens_used']
                                    summary.phases[phase_id]['cost'] += usage['estimated_cost']
                                    summary.phases[phase_id]['operations'] += 1

                    summary.operations_count = total_ops
                    summary.success_rate = successful_ops / max(total_ops, 1)

        except Exception as e:
            console.print(f"[yellow]Warning: Could not read workflow usage - {e}[/yellow]")

        return summary

    def check_coordination_budget(self, coordination_id: str,
                                coordination_budget: CoordinationBudget) -> Dict[str, Any]:
        """Check budget status for coordination session."""

        summary = self.get_coordination_summary(coordination_id)

        budget_status = {
            'coordination_id': coordination_id,
            'total_budget': coordination_budget.total_budget,
            'emergency_reserve': coordination_budget.emergency_reserve,
            'available_budget': coordination_budget.total_budget - coordination_budget.emergency_reserve,
            'used_budget': summary['total_cost'],
            'remaining_budget': coordination_budget.total_budget - summary['total_cost'],
            'budget_utilization': summary['total_cost'] / coordination_budget.total_budget,
            'within_budget': summary['total_cost'] <= coordination_budget.total_budget,
            'emergency_triggered': summary['total_cost'] > (coordination_budget.total_budget - coordination_budget.emergency_reserve),
            'workflows': {}
        }

        # Check individual workflow budgets
        for workflow_id, workflow_data in summary['workflows'].items():
            allocated = coordination_budget.workflow_allocations.get(workflow_id, coordination_budget.per_workflow_budget)
            workflow_budget_status = {
                'allocated': allocated,
                'used': workflow_data['total_cost'],
                'remaining': allocated - workflow_data['total_cost'],
                'utilization': workflow_data['total_cost'] / allocated if allocated > 0 else 0,
                'within_budget': workflow_data['total_cost'] <= allocated
            }
            budget_status['workflows'][workflow_id] = workflow_budget_status

        return budget_status

    def optimize_remaining_allocation(self, coordination_id: str,
                                    remaining_workflows: List[str],
                                    coordination_budget: CoordinationBudget) -> Dict[str, float]:
        """Optimize budget allocation for remaining workflows based on current usage."""

        current_summary = self.get_coordination_summary(coordination_id)
        remaining_budget = coordination_budget.total_budget - current_summary['total_cost']

        if remaining_budget <= coordination_budget.emergency_reserve:
            # Emergency mode: minimal allocation
            emergency_per_workflow = coordination_budget.emergency_reserve / max(len(remaining_workflows), 1)
            return {workflow_id: emergency_per_workflow for workflow_id in remaining_workflows}

        # Normal mode: distribute remaining budget proportionally
        available_budget = remaining_budget - coordination_budget.emergency_reserve
        per_workflow_allocation = available_budget / max(len(remaining_workflows), 1)

        return {workflow_id: min(per_workflow_allocation, coordination_budget.per_workflow_budget)
                for workflow_id in remaining_workflows}

    def _estimate_workflow_complexity(self, workflow: Dict[str, Any]) -> float:
        """Estimate workflow complexity for budget allocation."""

        complexity = 1.0

        # Factor in number of steps or phases
        steps = workflow.get('steps', [])
        phases = workflow.get('phases', [])

        if phases:
            complexity += len(phases) * 0.2
            # IPT-WT workflows tend to be more complex
            if any(phase.get('role') == 'ipt' for phase in phases):
                complexity += 0.5
        elif steps:
            complexity += len(steps) * 0.1

        # Factor in AI-heavy operations
        ai_steps = 0
        for step in steps:
            actor = step.get('actor', '')
            if 'ai_' in actor or actor in ['claude', 'gemini', 'aider']:
                ai_steps += 1

        complexity += ai_steps * 0.3

        # Factor in file scope size
        coordination = workflow.get('metadata', {}).get('coordination', {})
        file_scope = coordination.get('file_scope', [])
        if len(file_scope) > 10:
            complexity += 0.4

        return complexity

    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """Remove log entries older than specified days."""
        # This would implement log rotation in a full version
        # For now, just return 0 indicating no cleanup performed
        return 0
