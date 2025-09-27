"""
Workflow coordination and file scope management.

This module provides the core coordination infrastructure for multi-agent
workflow orchestration, including file scope conflict detection and resolution.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Any
from pathlib import Path
import fnmatch
import hashlib
import time
from enum import Enum


class CoordinationMode(Enum):
    """Workflow coordination modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    IPT_WT = "ipt_wt"
    MULTI_STREAM = "multi_stream"


class ScopeMode(Enum):
    """File scope access modes."""
    EXCLUSIVE = "exclusive"
    SHARED = "shared"
    READ_ONLY = "read-only"


@dataclass
class FileClaim:
    """Represents a file scope claim by a workflow."""
    workflow_id: str
    file_patterns: List[str]
    mode: ScopeMode = ScopeMode.EXCLUSIVE
    priority: int = 1
    phase_id: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.mode, str):
            self.mode = ScopeMode(self.mode)


@dataclass
class ScopeConflict:
    """Represents a conflict between file scope claims."""
    workflow_ids: List[str]
    conflicting_patterns: List[str]
    conflict_type: str  # "exclusive_overlap", "priority_collision"
    resolution_strategy: Optional[str] = None


@dataclass
class CoordinationPlan:
    """Plan for coordinating multiple workflows."""
    file_claims: List[FileClaim]
    execution_order: List[str] = None
    parallel_groups: List[List[str]] = None
    conflicts: List[ScopeConflict] = None

    def __post_init__(self):
        if self.execution_order is None:
            self.execution_order = []
        if self.parallel_groups is None:
            self.parallel_groups = []
        if self.conflicts is None:
            self.conflicts = []


class FileScopeManager:
    """Manages file scope claims and conflict detection."""

    def __init__(self):
        self.active_claims: Dict[str, FileClaim] = {}
        self.claim_history: List[FileClaim] = []

    def claim_files(self, workflow_id: str, file_patterns: List[str],
                   mode: ScopeMode = ScopeMode.EXCLUSIVE, priority: int = 1,
                   phase_id: Optional[str] = None) -> bool:
        """Claim file patterns for a workflow."""

        claim = FileClaim(workflow_id, file_patterns, mode, priority, phase_id)
        conflicts = self._check_claim_conflicts(claim)

        if conflicts:
            return False

        self.active_claims[workflow_id] = claim
        self.claim_history.append(claim)
        return True

    def detect_conflicts(self, claims: List[FileClaim]) -> List[ScopeConflict]:
        """Detect conflicts between file claims."""
        conflicts = []

        for i, claim1 in enumerate(claims):
            for claim2 in claims[i+1:]:
                if self._claims_conflict(claim1, claim2):
                    conflicts.append(ScopeConflict(
                        workflow_ids=[claim1.workflow_id, claim2.workflow_id],
                        conflicting_patterns=self._get_overlap(claim1, claim2),
                        conflict_type="exclusive_overlap"
                    ))

        return conflicts

    def release_claims(self, workflow_id: str) -> None:
        """Release file claims for a workflow."""
        if workflow_id in self.active_claims:
            del self.active_claims[workflow_id]

    def get_active_claims(self) -> Dict[str, FileClaim]:
        """Get all active file claims."""
        return self.active_claims.copy()

    def _check_claim_conflicts(self, new_claim: FileClaim) -> List[ScopeConflict]:
        """Check if a new claim conflicts with existing claims."""
        conflicts = []

        for existing_claim in self.active_claims.values():
            if self._claims_conflict(new_claim, existing_claim):
                conflicts.append(ScopeConflict(
                    workflow_ids=[new_claim.workflow_id, existing_claim.workflow_id],
                    conflicting_patterns=self._get_overlap(new_claim, existing_claim),
                    conflict_type="exclusive_overlap"
                ))

        return conflicts

    def _claims_conflict(self, claim1: FileClaim, claim2: FileClaim) -> bool:
        """Check if two claims conflict."""
        if claim1.mode == ScopeMode.READ_ONLY and claim2.mode == ScopeMode.READ_ONLY:
            return False

        # Check pattern overlap
        for pattern1 in claim1.file_patterns:
            for pattern2 in claim2.file_patterns:
                if self._patterns_overlap(pattern1, pattern2):
                    return True
        return False

    def _patterns_overlap(self, pattern1: str, pattern2: str) -> bool:
        """Check if two file patterns overlap."""
        # Convert patterns to normalized paths for comparison
        def normalize_pattern(pattern: str) -> Path:
            # Remove glob patterns for path comparison
            clean_pattern = pattern.replace("**", "").replace("*", "").strip("/\\")
            return Path(clean_pattern) if clean_pattern else Path(".")

        path1 = normalize_pattern(pattern1)
        path2 = normalize_pattern(pattern2)

        try:
            # Check if either path is a parent of the other
            path1.relative_to(path2)
            return True
        except ValueError:
            try:
                path2.relative_to(path1)
                return True
            except ValueError:
                # Check for exact pattern matches using fnmatch
                return fnmatch.fnmatch(pattern1, pattern2) or fnmatch.fnmatch(pattern2, pattern1)

    def _get_overlap(self, claim1: FileClaim, claim2: FileClaim) -> List[str]:
        """Get overlapping patterns between two claims."""
        overlaps = []

        for pattern1 in claim1.file_patterns:
            for pattern2 in claim2.file_patterns:
                if self._patterns_overlap(pattern1, pattern2):
                    overlaps.extend([pattern1, pattern2])

        return list(set(overlaps))


@dataclass
class ExecutionStatus:
    """Status of workflow execution coordination."""
    coordination_id: str
    active_workflows: int = 0
    completed_workflows: int = 0
    failed_workflows: int = 0
    total_cost_used: float = 0.0
    estimated_completion_time: Optional[str] = None


@dataclass
class DependencyNode:
    """Node in the workflow dependency graph."""
    id: str
    workflow_id: str
    phase_id: Optional[str] = None
    dependencies: List[str] = None
    can_start_immediately: bool = False

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class DependencyGraph:
    """Dependency graph for workflow coordination."""
    nodes: Dict[str, DependencyNode] = None
    execution_order: List[List[str]] = None  # Groups that can run in parallel

    def __post_init__(self):
        if self.nodes is None:
            self.nodes = {}
        if self.execution_order is None:
            self.execution_order = []


class WorkflowCoordinator:
    """Coordinates multiple workflow execution with dependency management."""

    def __init__(self):
        self.scope_manager = FileScopeManager()
        self.active_coordinations: Dict[str, Dict[str, Any]] = {}

    def create_coordination_plan(self, workflows: List[Dict[str, Any]]) -> CoordinationPlan:
        """Create coordination plan for workflow execution."""

        file_claims = []

        # Extract file scope from workflow phases or metadata
        for workflow in workflows:
            workflow_id = workflow.get('name', 'unnamed_workflow')

            # Check for coordination metadata
            coordination = workflow.get('metadata', {}).get('coordination', {})
            if coordination.get('file_scope'):
                claim = FileClaim(
                    workflow_id=workflow_id,
                    file_patterns=coordination['file_scope'],
                    mode=ScopeMode(coordination.get('scope_mode', 'exclusive')),
                    priority=coordination.get('priority', 1)
                )
                file_claims.append(claim)

            # Extract from phases if available
            for phase in workflow.get('phases', []):
                phase_scope = phase.get('file_scope', [])
                if phase_scope:
                    claim = FileClaim(
                        workflow_id=f"{workflow_id}_{phase['id']}",
                        file_patterns=phase_scope,
                        mode=ScopeMode(phase.get('scope_mode', 'exclusive')),
                        priority=phase.get('priority', 1),
                        phase_id=phase['id']
                    )
                    file_claims.append(claim)

        # Detect conflicts
        conflicts = self.scope_manager.detect_conflicts(file_claims)

        # Create execution order based on dependencies and conflicts
        execution_order = self._create_execution_order(workflows, conflicts)
        parallel_groups = self._create_parallel_groups(workflows, conflicts)

        return CoordinationPlan(
            file_claims=file_claims,
            execution_order=execution_order,
            parallel_groups=parallel_groups,
            conflicts=conflicts
        )

    def coordinate_parallel_workflows(self, workflows: List[Dict[str, Any]],
                                    coordination_id: str) -> CoordinationPlan:
        """Coordinate multiple workflows for parallel execution."""

        # Create dependency graph
        dependency_graph = self.create_dependency_graph(workflows)

        # Create coordination plan
        coordination_plan = self.create_coordination_plan(workflows)

        # Store coordination session
        self.active_coordinations[coordination_id] = {
            "workflows": workflows,
            "dependency_graph": dependency_graph,
            "coordination_plan": coordination_plan,
            "status": "planning",
            "start_time": time.time()
        }

        return coordination_plan

    def create_dependency_graph(self, workflows: List[Dict[str, Any]]) -> DependencyGraph:
        """Create dependency graph from workflow dependencies."""

        nodes = {}

        # Create nodes for each workflow and phase
        for workflow in workflows:
            workflow_id = workflow.get('name', 'unnamed_workflow')
            phases = workflow.get('phases', [])

            if phases:
                # IPT-WT pattern with phases
                for phase in phases:
                    phase_id = phase.get('id', 'unknown_phase')
                    node_id = f"{workflow_id}_{phase_id}"

                    dependencies = phase.get('depends_on', [])
                    # Convert relative dependencies to absolute node IDs
                    absolute_deps = []
                    for dep in dependencies:
                        if '_' in dep:
                            absolute_deps.append(dep)
                        else:
                            absolute_deps.append(f"{workflow_id}_{dep}")

                    nodes[node_id] = DependencyNode(
                        id=node_id,
                        workflow_id=workflow_id,
                        phase_id=phase_id,
                        dependencies=absolute_deps,
                        can_start_immediately=len(absolute_deps) == 0
                    )
            else:
                # Simple workflow without phases
                dependencies = workflow.get('depends_on', [])
                nodes[workflow_id] = DependencyNode(
                    id=workflow_id,
                    workflow_id=workflow_id,
                    dependencies=dependencies,
                    can_start_immediately=len(dependencies) == 0
                )

        # Create execution order based on dependencies
        execution_order = self._resolve_dependencies(nodes)

        return DependencyGraph(nodes=nodes, execution_order=execution_order)

    def monitor_execution(self, coordination_id: str) -> ExecutionStatus:
        """Monitor the execution status of a coordination session."""

        if coordination_id not in self.active_coordinations:
            return ExecutionStatus(coordination_id=coordination_id)

        coordination = self.active_coordinations[coordination_id]
        workflows = coordination["workflows"]

        # Simple status tracking (would be enhanced with real execution tracking)
        return ExecutionStatus(
            coordination_id=coordination_id,
            active_workflows=len(workflows),
            completed_workflows=0,
            failed_workflows=0,
            total_cost_used=0.0
        )

    def handle_workflow_completion(self, workflow_id: str, coordination_id: str,
                                 success: bool, cost_used: float = 0.0) -> None:
        """Handle completion of a workflow in a coordination session."""

        if coordination_id in self.active_coordinations:
            coordination = self.active_coordinations[coordination_id]

            # Update completion tracking
            if "completed_workflows" not in coordination:
                coordination["completed_workflows"] = []
            if "failed_workflows" not in coordination:
                coordination["failed_workflows"] = []

            if success:
                coordination["completed_workflows"].append(workflow_id)
            else:
                coordination["failed_workflows"].append(workflow_id)

            coordination["total_cost_used"] = coordination.get("total_cost_used", 0.0) + cost_used

            # Check if coordination is complete
            total_workflows = len(coordination["workflows"])
            completed_count = len(coordination["completed_workflows"]) + len(coordination["failed_workflows"])

            if completed_count >= total_workflows:
                coordination["status"] = "completed"
                coordination["end_time"] = time.time()

    def _create_execution_order(self, workflows: List[Dict[str, Any]],
                              conflicts: List[ScopeConflict]) -> List[str]:
        """Create execution order considering dependencies and conflicts."""
        order = []

        # Simple implementation: order by priority, then by dependency
        workflow_priorities = {}
        for workflow in workflows:
            workflow_id = workflow.get('name', 'unnamed_workflow')
            priority = workflow.get('metadata', {}).get('coordination', {}).get('priority', 1)
            workflow_priorities[workflow_id] = priority

        # Sort by priority (higher first)
        sorted_workflows = sorted(workflow_priorities.items(), key=lambda x: x[1], reverse=True)
        order = [workflow_id for workflow_id, _ in sorted_workflows]

        return order

    def _create_parallel_groups(self, workflows: List[Dict[str, Any]],
                              conflicts: List[ScopeConflict]) -> List[List[str]]:
        """Create groups of workflows that can run in parallel."""
        groups = []

        if not conflicts:
            # No conflicts, all can run in parallel
            workflow_ids = [w.get('name', 'unnamed_workflow') for w in workflows]
            if workflow_ids:
                groups.append(workflow_ids)
        else:
            # Group workflows that don't conflict with each other
            conflicting_workflows = set()
            for conflict in conflicts:
                conflicting_workflows.update(conflict.workflow_ids)

            non_conflicting = []
            conflicting_list = []

            for workflow in workflows:
                workflow_id = workflow.get('name', 'unnamed_workflow')
                if workflow_id in conflicting_workflows:
                    conflicting_list.append(workflow_id)
                else:
                    non_conflicting.append(workflow_id)

            if non_conflicting:
                groups.append(non_conflicting)

            # Add conflicting workflows as separate groups
            for workflow_id in conflicting_list:
                groups.append([workflow_id])

        return groups

    def _resolve_dependencies(self, nodes: Dict[str, DependencyNode]) -> List[List[str]]:
        """Resolve dependencies and create execution order groups."""

        execution_order = []
        remaining_nodes = set(nodes.keys())
        completed_nodes = set()

        while remaining_nodes:
            # Find nodes that can start (dependencies satisfied)
            ready_nodes = []
            for node_id in remaining_nodes:
                node = nodes[node_id]
                if all(dep in completed_nodes for dep in node.dependencies):
                    ready_nodes.append(node_id)

            if not ready_nodes:
                # Circular dependency or unresolvable - add remaining as final group
                execution_order.append(list(remaining_nodes))
                break

            # Add ready nodes as a parallel group
            execution_order.append(ready_nodes)

            # Mark as completed and remove from remaining
            completed_nodes.update(ready_nodes)
            remaining_nodes -= set(ready_nodes)

        return execution_order


# Export main classes
__all__ = [
    'CoordinationMode',
    'ScopeMode',
    'FileClaim',
    'ScopeConflict',
    'CoordinationPlan',
    'ExecutionStatus',
    'DependencyNode',
    'DependencyGraph',
    'FileScopeManager',
    'WorkflowCoordinator'
]