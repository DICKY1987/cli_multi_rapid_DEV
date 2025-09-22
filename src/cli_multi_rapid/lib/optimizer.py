"""
Predictive Cost & Performance Optimizer
Uses historical data to optimize tool selection and resource allocation
"""

import json
import logging
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolPerformanceMetrics:
    """Performance metrics for a specific tool."""

    tool_name: str
    avg_cost_per_task: float
    avg_duration_seconds: float
    success_rate: float
    cost_efficiency: float  # tasks per dollar
    time_efficiency: float  # tasks per minute
    quality_score: float  # based on rework frequency
    data_points: int = 0  # number of historical executions


@dataclass
class OptimizationRecommendation:
    """Recommendation for tool optimization."""

    recommended_tool: str
    confidence: float
    predicted_cost: float
    predicted_duration: float
    success_probability: float
    reasoning: str
    alternatives: list[tuple[str, float]]


class PredictiveOptimizer:
    """Optimizes tool selection based on historical performance."""

    def __init__(self, artifacts_dir: str = "artifacts", cost_dir: str = "cost"):
        self.artifacts_dir = Path(artifacts_dir)
        self.cost_dir = Path(cost_dir)
        self.tool_metrics: dict[str, ToolPerformanceMetrics] = {}
        self.execution_history: list[dict[str, Any]] = []
        self._load_historical_data()

    def _load_historical_data(self):
        """Load and analyze historical execution data."""
        executions = []

        # Load execution artifacts
        if self.artifacts_dir.exists():
            for artifact_file in self.artifacts_dir.glob("**/*.json"):
                try:
                    with open(artifact_file, encoding="utf-8") as f:
                        data = json.load(f)
                        executions.append(data)
                except Exception as e:
                    logger.warning(f"Failed to load artifact {artifact_file}: {e}")
                    continue

        # Load cost reports
        if self.cost_dir.exists():
            for cost_file in self.cost_dir.glob("**/*.json"):
                try:
                    with open(cost_file, encoding="utf-8") as f:
                        cost_data = json.load(f)
                        executions.append(cost_data)
                except Exception as e:
                    logger.warning(f"Failed to load cost data {cost_file}: {e}")
                    continue

        self.execution_history = executions
        logger.info(f"Loaded {len(executions)} historical execution records")

        # Calculate metrics per tool
        self._calculate_tool_metrics(executions)

    def _calculate_tool_metrics(self, executions: list[dict[str, Any]]):
        """Calculate performance metrics for each tool."""
        tool_data = {}

        for execution in executions:
            # Handle different data structures
            steps = []
            if "steps" in execution:
                steps = execution["steps"]
            elif "nodes" in execution:
                # DAG execution format
                for node in execution["nodes"]:
                    if "tool" in node:
                        steps.append(node)

            for step in steps:
                tool = step.get("tool", step.get("actor", "unknown"))

                if tool not in tool_data:
                    tool_data[tool] = {
                        "costs": [],
                        "durations": [],
                        "successes": [],
                        "rework_needed": [],
                        "total_executions": 0,
                    }

                # Collect metrics
                cost = step.get("cost", step.get("token_cost", 0))
                duration = step.get("duration_seconds", step.get("execution_time", 0))
                success = step.get("status", "unknown") in ["success", "completed"]
                rework = step.get("required_rework", step.get("needs_rework", False))

                tool_data[tool]["costs"].append(float(cost) if cost else 0)
                tool_data[tool]["durations"].append(float(duration) if duration else 0)
                tool_data[tool]["successes"].append(success)
                tool_data[tool]["rework_needed"].append(rework)
                tool_data[tool]["total_executions"] += 1

        # Calculate final metrics
        for tool, data in tool_data.items():
            if data["total_executions"] == 0:
                continue

            avg_cost = statistics.mean(data["costs"]) if data["costs"] else 0
            avg_duration = (
                statistics.mean(data["durations"]) if data["durations"] else 0
            )
            success_rate = (
                statistics.mean(data["successes"]) if data["successes"] else 0
            )
            rework_rate = (
                statistics.mean(data["rework_needed"]) if data["rework_needed"] else 0
            )

            cost_efficiency = (1 / avg_cost) if avg_cost > 0 else 1.0
            time_efficiency = (
                (60 / avg_duration) if avg_duration > 0 else 1.0
            )  # tasks per minute
            quality_score = max(0, 1 - rework_rate)  # Higher quality = less rework

            self.tool_metrics[tool] = ToolPerformanceMetrics(
                tool_name=tool,
                avg_cost_per_task=avg_cost,
                avg_duration_seconds=avg_duration,
                success_rate=success_rate,
                cost_efficiency=cost_efficiency,
                time_efficiency=time_efficiency,
                quality_score=quality_score,
                data_points=data["total_executions"],
            )

        logger.info(f"Calculated metrics for {len(self.tool_metrics)} tools")

    def recommend_tool_for_task(
        self,
        task_description: str,
        budget_limit: float = None,
        time_limit: int = None,
        priority: str = "balanced",
    ) -> OptimizationRecommendation:
        """Recommend optimal tool for a given task."""

        # Analyze task characteristics
        task_complexity = self._estimate_task_complexity(task_description)
        self._extract_required_capabilities(task_description)

        # Score each tool
        tool_scores = {}
        for tool_name, metrics in self.tool_metrics.items():
            score = self._calculate_tool_score(
                metrics, task_complexity, budget_limit, time_limit, priority
            )
            tool_scores[tool_name] = score

        # Handle case with no historical data
        if not tool_scores:
            # Provide default recommendation based on task type
            default_tool = self._get_default_tool_for_task(task_description)
            return OptimizationRecommendation(
                recommended_tool=default_tool,
                confidence=0.3,  # Low confidence without historical data
                predicted_cost=100.0,  # Conservative estimate
                predicted_duration=300.0,  # 5 minutes default
                success_probability=0.8,
                reasoning="No historical data available, using default tool mapping",
                alternatives=[],
            )

        # Get best recommendation
        best_tool = max(tool_scores.keys(), key=lambda t: tool_scores[t]["total_score"])
        best_metrics = self.tool_metrics[best_tool]

        # Calculate predicted values
        predicted_cost = best_metrics.avg_cost_per_task * task_complexity
        predicted_duration = best_metrics.avg_duration_seconds * task_complexity

        # Generate reasoning
        reasoning = self._generate_reasoning(
            best_tool, tool_scores[best_tool], priority
        )

        # Get alternatives
        alternatives = sorted(
            [(tool, score["total_score"]) for tool, score in tool_scores.items()],
            key=lambda x: x[1],
            reverse=True,
        )[
            1:4
        ]  # Top 3 alternatives

        return OptimizationRecommendation(
            recommended_tool=best_tool,
            confidence=tool_scores[best_tool]["confidence"],
            predicted_cost=predicted_cost,
            predicted_duration=predicted_duration,
            success_probability=best_metrics.success_rate,
            reasoning=reasoning,
            alternatives=alternatives,
        )

    def _estimate_task_complexity(self, task_description: str) -> float:
        """Estimate task complexity (0.5 = simple, 2.0 = very complex)."""
        complexity_indicators = {
            "simple": [
                "fix typo",
                "update comment",
                "add log",
                "format",
                "rename",
                "delete",
            ],
            "medium": [
                "implement",
                "add feature",
                "refactor",
                "optimize",
                "update",
                "modify",
            ],
            "complex": [
                "architecture",
                "design",
                "integrate",
                "security",
                "performance",
                "migration",
            ],
            "very_complex": [
                "complete rewrite",
                "new system",
                "algorithm design",
                "full implementation",
            ],
        }

        task_lower = task_description.lower()
        word_count = len(task_description.split())

        # Base complexity from keywords
        base_complexity = 1.0
        for level, indicators in complexity_indicators.items():
            if any(indicator in task_lower for indicator in indicators):
                if level == "simple":
                    base_complexity = 0.5
                elif level == "medium":
                    base_complexity = 1.0
                elif level == "complex":
                    base_complexity = 1.5
                elif level == "very_complex":
                    base_complexity = 2.0
                break

        # Adjust based on description length
        length_factor = min(
            1.5, word_count / 10
        )  # Longer descriptions suggest complexity

        return min(3.0, base_complexity * length_factor)

    def _extract_required_capabilities(self, task_description: str) -> list[str]:
        """Extract required capabilities from task description."""
        capabilities = []
        task_lower = task_description.lower()

        capability_keywords = {
            "python": ["python", "django", "flask", "fastapi", "py", "pip"],
            "javascript": ["javascript", "js", "node", "react", "vue", "npm"],
            "web": ["web", "html", "css", "frontend", "backend"],
            "security": [
                "security",
                "auth",
                "oauth",
                "encrypt",
                "secure",
                "vulnerability",
            ],
            "database": ["database", "sql", "postgres", "mysql", "db", "sqlite"],
            "testing": ["test", "unittest", "pytest", "spec", "coverage"],
            "documentation": [
                "docs",
                "documentation",
                "readme",
                "comment",
                "docstring",
            ],
            "api": ["api", "rest", "graphql", "endpoint", "service"],
            "git": ["git", "commit", "branch", "merge", "repository"],
            "deployment": ["deploy", "docker", "kubernetes", "ci/cd", "pipeline"],
        }

        for capability, keywords in capability_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                capabilities.append(capability)

        return capabilities

    def _calculate_tool_score(
        self,
        metrics: ToolPerformanceMetrics,
        complexity: float,
        budget_limit: Optional[float],
        time_limit: Optional[int],
        priority: str,
    ) -> dict[str, float]:
        """Calculate composite score for tool selection."""

        # Base scores (0-1)
        cost_score = min(
            1.0, metrics.cost_efficiency / 10.0
        )  # Normalize cost efficiency
        time_score = min(
            1.0, metrics.time_efficiency / 5.0
        )  # Normalize time efficiency
        quality_score = metrics.quality_score
        success_score = metrics.success_rate

        # Apply constraints
        predicted_cost = metrics.avg_cost_per_task * complexity
        predicted_time = metrics.avg_duration_seconds * complexity

        # Penalty for constraint violations
        cost_penalty = 0
        time_penalty = 0

        if budget_limit and predicted_cost > budget_limit:
            cost_penalty = 0.5  # Heavy penalty for budget overrun

        if time_limit and predicted_time > time_limit:
            time_penalty = 0.5  # Heavy penalty for time overrun

        # Priority weighting
        weights = {
            "cost": {"cost": 0.4, "time": 0.2, "quality": 0.2, "success": 0.2},
            "speed": {"cost": 0.1, "time": 0.4, "quality": 0.2, "success": 0.3},
            "quality": {"cost": 0.1, "time": 0.2, "quality": 0.4, "success": 0.3},
            "balanced": {"cost": 0.25, "time": 0.25, "quality": 0.25, "success": 0.25},
        }

        weight = weights.get(priority, weights["balanced"])

        # Calculate weighted score
        total_score = (
            (
                cost_score * weight["cost"]
                + time_score * weight["time"]
                + quality_score * weight["quality"]
                + success_score * weight["success"]
            )
            - cost_penalty
            - time_penalty
        )

        # Confidence based on data quantity and recency
        confidence = min(
            1.0, metrics.data_points / 10.0
        )  # Full confidence with 10+ data points

        return {
            "total_score": max(0, total_score),
            "confidence": confidence,
            "cost_score": cost_score,
            "time_score": time_score,
            "quality_score": quality_score,
            "success_score": success_score,
            "cost_penalty": cost_penalty,
            "time_penalty": time_penalty,
        }

    def _get_default_tool_for_task(self, task_description: str) -> str:
        """Get default tool recommendation when no historical data exists."""
        task_lower = task_description.lower()

        # Simple heuristics for tool selection
        if any(word in task_lower for word in ["python", "pip", "django", "flask"]):
            return "python_tools"
        elif any(word in task_lower for word in ["javascript", "node", "npm", "react"]):
            return "javascript_tools"
        elif any(word in task_lower for word in ["test", "unittest", "pytest"]):
            return "testing_tools"
        elif any(word in task_lower for word in ["docs", "documentation", "readme"]):
            return "documentation_tools"
        elif any(word in task_lower for word in ["git", "commit", "branch"]):
            return "git_ops"
        else:
            return "general_tools"

    def _generate_reasoning(
        self, tool: str, scores: dict[str, float], priority: str
    ) -> str:
        """Generate human-readable reasoning for tool selection."""
        reasoning_parts = []

        if scores["confidence"] < 0.5:
            reasoning_parts.append("Limited historical data")
        else:
            reasoning_parts.append("Based on historical performance")

        if priority == "cost" and scores["cost_score"] > 0.7:
            reasoning_parts.append("excellent cost efficiency")
        elif priority == "speed" and scores["time_score"] > 0.7:
            reasoning_parts.append("superior speed performance")
        elif priority == "quality" and scores["quality_score"] > 0.8:
            reasoning_parts.append("high quality track record")

        if scores["success_score"] > 0.9:
            reasoning_parts.append("very high success rate")

        if scores["cost_penalty"] > 0:
            reasoning_parts.append("WARNING: may exceed budget")
        if scores["time_penalty"] > 0:
            reasoning_parts.append("WARNING: may exceed time limit")

        return f"{tool} selected: " + ", ".join(reasoning_parts)

    def optimize_parallel_plan(
        self, nodes: list[dict[str, Any]], global_budget: Optional[float] = None
    ) -> list[dict[str, Any]]:
        """Optimize tool selection for all nodes in a parallel plan."""
        optimized_nodes = []
        total_predicted_cost = 0

        for node in nodes:
            task_desc = node.get("goal", node.get("name", ""))
            current_tool = node.get("tool", node.get("actor"))

            # Calculate remaining budget
            remaining_budget = None
            if global_budget:
                remaining_budget = global_budget - total_predicted_cost

            # Get recommendation
            recommendation = self.recommend_tool_for_task(
                task_desc,
                budget_limit=remaining_budget or node.get("budget_limit"),
                time_limit=node.get("time_limit"),
                priority=node.get("priority", "balanced"),
            )

            # Update node
            optimized_node = node.copy()
            recommended_tool = recommendation.recommended_tool

            # Only change if confidence is reasonable and tool is different
            if (
                recommendation.confidence > 0.5
                and current_tool != recommended_tool
                and current_tool is not None
            ):

                optimized_node["tool"] = recommended_tool
                optimized_node["optimization"] = {
                    "original_tool": current_tool,
                    "reason": recommendation.reasoning,
                    "confidence": recommendation.confidence,
                    "predicted_improvement": {
                        "cost": recommendation.predicted_cost,
                        "duration": recommendation.predicted_duration,
                        "success_probability": recommendation.success_probability,
                    },
                }

            # Track cost for budget management
            total_predicted_cost += recommendation.predicted_cost

            optimized_nodes.append(optimized_node)

        return optimized_nodes

    def get_optimization_stats(self) -> dict[str, Any]:
        """Get optimization statistics and tool performance summary."""
        if not self.tool_metrics:
            return {"error": "No historical data available"}

        tools_summary = {}
        for tool, metrics in self.tool_metrics.items():
            tools_summary[tool] = {
                "avg_cost": metrics.avg_cost_per_task,
                "avg_duration": metrics.avg_duration_seconds,
                "success_rate": metrics.success_rate,
                "quality_score": metrics.quality_score,
                "data_points": metrics.data_points,
            }

        # Find best tools by category
        best_cost = min(self.tool_metrics.values(), key=lambda m: m.avg_cost_per_task)
        best_speed = min(
            self.tool_metrics.values(), key=lambda m: m.avg_duration_seconds
        )
        best_quality = max(self.tool_metrics.values(), key=lambda m: m.quality_score)

        return {
            "total_tools_analyzed": len(self.tool_metrics),
            "total_executions": len(self.execution_history),
            "tools_summary": tools_summary,
            "best_performers": {
                "cost_efficient": best_cost.tool_name,
                "fastest": best_speed.tool_name,
                "highest_quality": best_quality.tool_name,
            },
        }

    def save_metrics(self, file_path: Path):
        """Save tool metrics to file."""
        metrics_data = {
            "generated_at": datetime.utcnow().isoformat(),
            "tool_metrics": {
                tool: asdict(metrics) for tool, metrics in self.tool_metrics.items()
            },
            "stats": self.get_optimization_stats(),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(metrics_data, f, indent=2)


# CLI Integration functions
def analyze_performance_command(artifacts_dir: str = "artifacts") -> dict[str, Any]:
    """Analyze tool performance from historical data."""
    optimizer = PredictiveOptimizer(artifacts_dir)
    return optimizer.get_optimization_stats()


def optimize_plan_command(
    plan_file: str, priority: str = "balanced", output_file: str = None
) -> bool:
    """Optimize tool selection in a workflow plan."""
    optimizer = PredictiveOptimizer()

    try:
        # Load plan
        with open(plan_file, encoding="utf-8") as f:
            if plan_file.endswith(".json"):
                plan = json.load(f)
            else:
                import yaml

                plan = yaml.safe_load(f)

        # Optimize
        nodes = plan.get("nodes", [])
        if not nodes:
            logger.warning("No nodes found in plan")
            return False

        logger.info(f"Analyzing plan with {len(nodes)} nodes...")
        global_budget = plan.get("global_budget_usd")
        optimized_nodes = optimizer.optimize_parallel_plan(nodes, global_budget)

        # Show optimizations
        changes = 0
        for original, optimized in zip(nodes, optimized_nodes):
            if "optimization" in optimized:
                changes += 1
                logger.info(
                    f"Optimized {optimized.get('id', 'unknown')}: "
                    f"{original.get('tool', 'unknown')} → {optimized['tool']}"
                )

        if changes == 0:
            logger.info("No optimizations found - plan is already optimal!")
        else:
            # Save optimized plan
            plan["nodes"] = optimized_nodes

            if not output_file:
                name_part = Path(plan_file).stem
                suffix = Path(plan_file).suffix
                output_file = f"{name_part}_optimized{suffix}"

            with open(output_file, "w", encoding="utf-8") as f:
                if output_file.endswith(".json"):
                    json.dump(plan, f, indent=2)
                else:
                    import yaml

                    yaml.dump(plan, f, default_flow_style=False)

            logger.info(f"Saved optimized plan: {output_file}")

        return True

    except Exception as e:
        logger.error(f"Failed to optimize plan: {e}")
        return False


# Example usage
def example_usage():
    """Example of using the predictive optimizer."""
    optimizer = PredictiveOptimizer()

    # Analyze a task
    task = (
        "Implement OAuth2 authentication for Python Flask API with PostgreSQL backend"
    )
    recommendation = optimizer.recommend_tool_for_task(task, priority="quality")

    print(f"Task: {task}")
    print(f"Recommended tool: {recommendation.recommended_tool}")
    print(f"Confidence: {recommendation.confidence:.2f}")
    print(f"Reasoning: {recommendation.reasoning}")

    # Show performance stats
    stats = optimizer.get_optimization_stats()
    print(f"\nAnalyzed {stats.get('total_tools_analyzed', 0)} tools")
    print(f"Best performers: {stats.get('best_performers', {})}")


if __name__ == "__main__":
    example_usage()
