"""
Enhanced Parallel Workflow Scheduler
Extends existing scheduler with path claims and conflict detection
"""

import asyncio
import fnmatch
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PathClaim:
    """Represents a file path claim by a workflow node."""

    path: str
    mode: str  # "exclusive" or "shared"
    node_id: str


class ConflictDetector:
    """Detects path conflicts between parallel workflow nodes."""

    def __init__(self):
        self.active_claims: list[PathClaim] = []

    def check_conflicts(self, new_claims: list[PathClaim]) -> list[str]:
        """Check if new claims conflict with active ones."""
        conflicts = []

        for new_claim in new_claims:
            for active_claim in self.active_claims:
                if self._paths_overlap(new_claim.path, active_claim.path):
                    # Exclusive conflicts with everything
                    if (
                        new_claim.mode == "exclusive"
                        or active_claim.mode == "exclusive"
                    ):
                        conflicts.append(
                            f"Path conflict: {new_claim.node_id}({new_claim.path}) "
                            f"vs {active_claim.node_id}({active_claim.path})"
                        )

        return conflicts

    def _paths_overlap(self, path1: str, path2: str) -> bool:
        """Check if two path patterns overlap."""
        # Simple glob-based overlap detection
        return (
            fnmatch.fnmatch(path1, path2)
            or fnmatch.fnmatch(path2, path1)
            or path1 == path2
        )

    def claim_paths(self, claims: list[PathClaim]):
        """Register new path claims."""
        self.active_claims.extend(claims)

    def release_paths(self, node_id: str):
        """Release all path claims for a node."""
        self.active_claims = [c for c in self.active_claims if c.node_id != node_id]


class ParallelWorkflowScheduler:
    """Enhanced scheduler with parallel execution and conflict detection."""

    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent
        self.conflict_detector = ConflictDetector()
        self.running_nodes: set[str] = set()
        self.completed_nodes: set[str] = set()
        self.failed_nodes: set[str] = set()
        self.node_tasks: dict[str, asyncio.Task] = {}
        self.event_handlers = []

    def add_event_handler(self, handler):
        """Add event handler for workflow events."""
        self.event_handlers.append(handler)

    def _emit_node_event(self, event_type: str, node_id: str, data: dict[str, Any]):
        """Emit workflow events to registered handlers."""
        event = {
            "type": f"workflow.node.{event_type}",
            "timestamp": datetime.utcnow().isoformat(),
            "node_id": node_id,
            "data": data,
        }

        # Send to event handlers
        for handler in self.event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.warning(f"Event handler failed: {e}")

        # Also write to structured logs
        logger.info(f"Workflow event: {event}")

    async def execute_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute a DAG plan with parallel workflow support."""
        logger.info(f"Starting execution of plan {plan.get('plan_id', 'unknown')}")

        nodes = {node["id"]: node for node in plan["nodes"]}

        # Build dependency graph
        dependency_graph = self._build_dependency_graph(nodes)

        # Execute nodes in parallel where possible
        while not self._all_nodes_processed(nodes):
            # Find ready nodes (dependencies satisfied, no conflicts)
            ready_nodes = self._find_ready_nodes(nodes, dependency_graph)

            # Start execution for ready nodes (up to concurrency limit)
            await self._start_ready_nodes(ready_nodes, nodes)

            # Wait for at least one task to complete
            if self.node_tasks:
                done, pending = await asyncio.wait(
                    self.node_tasks.values(), return_when=asyncio.FIRST_COMPLETED
                )

                # Process completed tasks
                for task in done:
                    await self._handle_completed_task(task)

            # Small delay to prevent busy waiting
            await asyncio.sleep(0.1)

        result = {
            "plan_id": plan.get("plan_id"),
            "completed": list(self.completed_nodes),
            "failed": list(self.failed_nodes),
            "success": len(self.failed_nodes) == 0,
            "execution_time": datetime.utcnow().isoformat(),
        }

        logger.info(f"Plan execution completed: {result}")
        return result

    def _build_dependency_graph(self, nodes: dict[str, Any]) -> dict[str, set[str]]:
        """Build dependency graph from nodes."""
        graph = {}
        for node_id, node in nodes.items():
            graph[node_id] = set(node.get("dependencies", []))
        return graph

    def _find_ready_nodes(
        self, nodes: dict[str, Any], dependency_graph: dict[str, set[str]]
    ) -> list[str]:
        """Find nodes that are ready to execute."""
        ready = []

        for node_id, node in nodes.items():
            if (
                node_id not in self.running_nodes
                and node_id not in self.completed_nodes
                and node_id not in self.failed_nodes
            ):

                # Check if dependencies are satisfied
                dependencies = dependency_graph.get(node_id, set())
                if dependencies.issubset(self.completed_nodes):

                    # Check for path conflicts
                    claims = self._extract_path_claims(node_id, node)
                    conflicts = self.conflict_detector.check_conflicts(claims)

                    if not conflicts:
                        ready.append(node_id)
                    else:
                        logger.debug(
                            f"Node {node_id} blocked by path conflicts: {conflicts}"
                        )

        return ready

    def _extract_path_claims(
        self, node_id: str, node: dict[str, Any]
    ) -> list[PathClaim]:
        """Extract path claims from a node definition."""
        claims = []
        for claim_data in node.get("path_claims", []):
            claims.append(
                PathClaim(
                    path=claim_data["path"], mode=claim_data["mode"], node_id=node_id
                )
            )
        return claims

    async def _start_ready_nodes(self, ready_nodes: list[str], nodes: dict[str, Any]):
        """Start execution for ready nodes up to concurrency limit."""
        available_slots = self.max_concurrent - len(self.running_nodes)

        for node_id in ready_nodes[:available_slots]:
            node = nodes[node_id]

            # Claim paths
            claims = self._extract_path_claims(node_id, node)
            self.conflict_detector.claim_paths(claims)

            # Emit start event
            self._emit_node_event(
                "started", node_id, {"tool": node.get("tool"), "goal": node.get("goal")}
            )

            # Start execution
            task = asyncio.create_task(self._execute_node(node_id, node))
            self.node_tasks[node_id] = task
            self.running_nodes.add(node_id)

            logger.info(
                f"Started execution for node {node_id} using tool {node.get('tool')}"
            )

    async def _execute_node(self, node_id: str, node: dict[str, Any]) -> dict[str, Any]:
        """Execute a single workflow node."""
        try:
            # Simulate tool execution
            tool = node.get("tool")
            goal = node.get("goal")

            logger.info(f"Executing {node_id}: {goal} using {tool}")

            # Here you would integrate with your actual tool adapters
            # For now, simulate work based on estimated cost/complexity
            estimated_cost = node.get("estimated_cost", 1000)
            sleep_time = min(estimated_cost / 1000, 5)  # Max 5 seconds
            await asyncio.sleep(sleep_time)

            # Emit progress event
            self._emit_node_event(
                "progress", node_id, {"status": "executing", "progress": 50}
            )

            return {
                "node_id": node_id,
                "status": "completed",
                "result": f"Successfully completed {goal}",
                "tool_used": tool,
                "execution_time": sleep_time,
            }

        except Exception as e:
            logger.error(f"Node {node_id} failed: {e}")
            return {
                "node_id": node_id,
                "status": "failed",
                "error": str(e),
                "tool_used": tool,
            }

    async def _handle_completed_task(self, task: asyncio.Task):
        """Handle a completed workflow node task."""
        result = await task
        node_id = result["node_id"]

        # Remove from running
        self.running_nodes.discard(node_id)
        self.node_tasks.pop(node_id, None)

        # Release path claims
        self.conflict_detector.release_paths(node_id)

        # Update status and emit events
        if result["status"] == "completed":
            self.completed_nodes.add(node_id)
            self._emit_node_event("completed", node_id, result)
            logger.info(f"✅ Node {node_id} completed successfully")
        else:
            self.failed_nodes.add(node_id)
            self._emit_node_event("failed", node_id, result)
            logger.error(f"❌ Node {node_id} failed: {result.get('error')}")

    def _all_nodes_processed(self, nodes: dict[str, Any]) -> bool:
        """Check if all nodes have been processed."""
        total_nodes = len(nodes)
        processed_nodes = len(self.completed_nodes) + len(self.failed_nodes)
        return processed_nodes == total_nodes


# Example usage
async def example_usage():
    """Example of how to use the parallel scheduler."""
    plan = {
        "plan_id": "example_plan",
        "nodes": [
            {
                "id": "n1",
                "tool": "aider",
                "goal": "Implement OAuth2 middleware",
                "path_claims": [{"path": "src/auth/**", "mode": "exclusive"}],
                "dependencies": [],
                "estimated_cost": 2000,
            },
            {
                "id": "n2",
                "tool": "claude-cli",
                "goal": "Add tests",
                "path_claims": [{"path": "tests/**", "mode": "exclusive"}],
                "dependencies": ["n1"],
                "estimated_cost": 1500,
            },
            {
                "id": "n3",
                "tool": "cursor",
                "goal": "Update docs",
                "path_claims": [{"path": "docs/**", "mode": "exclusive"}],
                "dependencies": ["n1"],
                "estimated_cost": 1000,
            },
        ],
    }

    scheduler = ParallelWorkflowScheduler(max_concurrent=2)
    result = await scheduler.execute_plan(plan)
    print(f"Execution result: {result}")


if __name__ == "__main__":
    asyncio.run(example_usage())
