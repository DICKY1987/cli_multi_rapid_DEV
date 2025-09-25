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
from typing import Any, Optional

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


@dataclass
class BudgetLimit:
    """Budget enforcement configuration."""

    daily_token_limit: int = 100000
    daily_cost_limit: float = 10.0
    per_workflow_limit: int = 50000
    warn_threshold: float = 0.8


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

    def get_daily_usage(self, target_date: Optional[date] = None) -> dict[str, Any]:
        """Get token usage summary for a specific date."""
        if target_date is None:
            target_date = date.today()

        target_date_str = target_date.isoformat()

        daily_tokens = 0
        daily_cost = 0.0
        operations = []

        try:
            if self.usage_file.exists():
                with open(self.usage_file, encoding="utf-8") as f:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        """Generate usage and cost report."""

        if last_run:
            # Get most recent operation
            operations = []
            try:
                if self.usage_file.exists():
                    with open(self.usage_file, encoding="utf-8") as f:
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

    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """Remove log entries older than specified days."""
        # This would implement log rotation in a full version
        # For now, just return 0 indicating no cleanup performed
        return 0
