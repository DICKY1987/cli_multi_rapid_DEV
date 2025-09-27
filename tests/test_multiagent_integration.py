#!/usr/bin/env python3
"""
Integration tests for multi-agent orchestration system.

Tests the complete multi-agent workflow coordination, including:
- File scope conflict detection
- Parallel execution planning
- Merge queue management
- Cost tracking and budgeting
- Security isolation
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from src.cli_multi_rapid.workflow_runner import WorkflowRunner, CoordinatedWorkflowResult
from src.cli_multi_rapid.coordination import (
    WorkflowCoordinator, FileScopeManager, CoordinationMode, ScopeMode
)
from src.cli_multi_rapid.coordination.merge_queue import MergeQueueManager, MergeStatus
from src.cli_multi_rapid.coordination.security import SecurityManager, SecurityLevel
from src.cli_multi_rapid.router import Router, ParallelRoutingPlan
from src.cli_multi_rapid.cost_tracker import CostTracker, CoordinationBudget


class TestMultiAgentIntegration:
    """Integration tests for multi-agent orchestration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.workflow_runner = WorkflowRunner()
        self.coordinator = WorkflowCoordinator()
        self.router = Router()
        self.cost_tracker = CostTracker(logs_dir=str(self.temp_dir / "logs"))
        self.security_manager = SecurityManager(self.temp_dir / "security")
        self.merge_queue = MergeQueueManager(self.temp_dir / "merge_queue.json")

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_coordination_plan_creation(self):
        """Test creation of coordination plan with file scope conflict detection."""

        workflows = [
            {
                'name': 'workflow_a',
                'metadata': {
                    'coordination': {
                        'file_scope': ['src/module_a.py', 'src/shared.py'],
                        'scope_mode': 'exclusive',
                        'priority': 3
                    }
                }
            },
            {
                'name': 'workflow_b',
                'metadata': {
                    'coordination': {
                        'file_scope': ['src/module_b.py', 'src/shared.py'],
                        'scope_mode': 'exclusive',
                        'priority': 2
                    }
                }
            },
            {
                'name': 'workflow_c',
                'metadata': {
                    'coordination': {
                        'file_scope': ['tests/**/*.py'],
                        'scope_mode': 'shared',
                        'priority': 1
                    }
                }
            }
        ]

        coordination_plan = self.coordinator.create_coordination_plan(workflows)

        # Should detect conflict between workflow_a and workflow_b on shared.py
        assert len(coordination_plan.conflicts) == 1
        conflict = coordination_plan.conflicts[0]
        assert 'workflow_a' in conflict.workflow_ids
        assert 'workflow_b' in conflict.workflow_ids
        assert 'src/shared.py' in conflict.conflicting_patterns

        # Should create execution order based on priority
        assert coordination_plan.execution_order == ['workflow_a', 'workflow_b', 'workflow_c']

        # Should group non-conflicting workflows together
        assert len(coordination_plan.parallel_groups) >= 1
        # workflow_c should be able to run in parallel with others due to shared scope

    def test_parallel_routing_plan(self):
        """Test parallel routing with resource allocation."""

        steps = [
            {
                'id': 'step1',
                'actor': 'code_fixers',
                'file_scope': ['src/module_a.py']
            },
            {
                'id': 'step2',
                'actor': 'ai_editor',
                'file_scope': ['src/module_b.py']
            },
            {
                'id': 'step3',
                'actor': 'pytest_runner',
                'file_scope': ['tests/']
            }
        ]

        routing_plan = self.router.route_parallel_steps(steps)

        assert isinstance(routing_plan, ParallelRoutingPlan)
        assert len(routing_plan.routing_decisions) == 3
        assert len(routing_plan.execution_groups) >= 1
        assert routing_plan.total_estimated_cost >= 0

        # Should have resource allocation mapping
        assert 'code_fixers' in routing_plan.resource_allocation
        assert 'ai_editor' in routing_plan.resource_allocation
        assert 'pytest_runner' in routing_plan.resource_allocation

    def test_budget_allocation_and_tracking(self):
        """Test cost tracking and budget allocation for coordinated workflows."""

        workflows = [
            {
                'name': 'high_priority_workflow',
                'metadata': {
                    'coordination': {'priority': 4}
                },
                'steps': [
                    {'actor': 'ai_editor', 'id': 'edit1'},
                    {'actor': 'ai_analyst', 'id': 'analyze1'}
                ]
            },
            {
                'name': 'low_priority_workflow',
                'metadata': {
                    'coordination': {'priority': 1}
                },
                'steps': [
                    {'actor': 'code_fixers', 'id': 'fix1'}
                ]
            }
        ]

        coordination_budget = CoordinationBudget(
            total_budget=20.0,
            per_workflow_budget=15.0,
            emergency_reserve=3.0
        )

        # Test budget allocation
        allocations = self.cost_tracker.allocate_budget(workflows, coordination_budget)

        assert 'high_priority_workflow' in allocations
        assert 'low_priority_workflow' in allocations
        # High priority should get more budget
        assert allocations['high_priority_workflow'] > allocations['low_priority_workflow']

        # Test cost tracking
        coordination_id = "coord_20240101_120000"

        # Simulate cost tracking
        self.cost_tracker.track_coordinated_cost(
            coordination_id=coordination_id,
            workflow_id='high_priority_workflow',
            operation='ai_edit',
            tokens_used=1000,
            model='claude-3'
        )

        # Test budget checking
        budget_status = self.cost_tracker.check_coordination_budget(
            coordination_id, coordination_budget
        )

        assert budget_status['coordination_id'] == coordination_id
        assert budget_status['within_budget'] is True
        assert 'high_priority_workflow' in budget_status['workflows']

    def test_merge_queue_integration(self):
        """Test merge queue management with quality gates."""

        # Add items to merge queue
        success1 = self.merge_queue.add_to_queue(
            branch='feature/workflow-a',
            workflow_id='workflow_a',
            priority=3,
            verification_level='standard'
        )

        success2 = self.merge_queue.add_to_queue(
            branch='feature/workflow-b',
            workflow_id='workflow_b',
            priority=1,
            verification_level='minimal'
        )

        assert success1 is True
        assert success2 is True

        # Check queue status
        status = self.merge_queue.get_queue_status()
        assert status['total_items'] == 2
        assert status['queue_length'] == 2

        # Get next item (should be highest priority)
        next_item = self.merge_queue.get_next_item()
        assert next_item is not None
        assert next_item.priority == 3
        assert next_item.branch == 'feature/workflow-a'

        # Update item status
        self.merge_queue.update_item_status(
            'feature/workflow-a',
            MergeStatus.MERGED,
            merge_commit='abc123def456'
        )

        # Verify status update
        item = self.merge_queue.get_item_by_branch('feature/workflow-a')
        assert item.status == MergeStatus.MERGED
        assert item.merge_commit == 'abc123def456'

    def test_security_isolation(self):
        """Test security context creation and validation."""

        coordination_metadata = {
            'coordination': {
                'file_scope': ['src/**/*.py', 'tests/**/*.py'],
                'risk_level': 'medium'
            }
        }

        # Create security context
        workflow_id = 'test_workflow'
        security_context = self.security_manager.create_security_context(
            workflow_id, coordination_metadata
        )

        assert security_context.workflow_id == workflow_id
        assert security_context.security_level == SecurityLevel.MEDIUM
        assert 'src/**/*.py' in security_context.allowed_paths

        # Test file access validation
        from src.cli_multi_rapid.coordination.security import AccessMode

        # Should allow access to files in scope
        assert self.security_manager.validate_file_access(
            workflow_id, 'src/test.py', AccessMode.READ_WRITE
        ) is True

        # Should deny access to forbidden paths
        assert self.security_manager.validate_file_access(
            workflow_id, '/etc/passwd', AccessMode.READ_ONLY
        ) is False

        # Test command validation
        assert self.security_manager.validate_command_execution(
            workflow_id, 'git status'
        ) is True

        # Create isolation environment
        isolation_env = self.security_manager.create_isolation_environment(
            workflow_id, security_context
        )

        assert isolation_env.workflow_id == workflow_id
        assert isolation_env.temp_directory.exists()
        assert 'WORKFLOW_ID' in isolation_env.environment_variables

        # Cleanup
        success = self.security_manager.cleanup_environment(workflow_id)
        assert success is True

    def test_end_to_end_coordination(self):
        """Test complete end-to-end multi-agent coordination."""

        # Create test workflow files
        workflow_files = []
        for i in range(2):
            workflow_content = {
                'name': f'test_workflow_{i}',
                'version': '1.0',
                'metadata': {
                    'orchestration_pattern': 'parallel',
                    'coordination': {
                        'file_scope': [f'src/module_{i}.py'],
                        'priority': i + 1,
                        'risk_level': 'low'
                    }
                },
                'steps': [
                    {
                        'id': f'{i}.001',
                        'name': f'Test step {i}',
                        'actor': 'code_fixers',
                        'with': {'tools': ['black']}
                    }
                ]
            }

            workflow_file = self.temp_dir / f'test_workflow_{i}.yaml'
            with open(workflow_file, 'w') as f:
                json.dump(workflow_content, f, indent=2)
            workflow_files.append(workflow_file)

        # Execute coordinated workflows
        result = self.workflow_runner.run_coordinated_workflows(
            workflow_files=workflow_files,
            coordination_mode='parallel',
            max_parallel=2,
            dry_run=True  # Safe for testing
        )

        assert isinstance(result, CoordinatedWorkflowResult)
        assert result.success is True
        assert len(result.workflow_results) == 2
        assert result.total_execution_time > 0
        assert result.parallel_efficiency >= 0

        # Verify all workflows completed
        for workflow_id, workflow_result in result.workflow_results.items():
            assert workflow_result.success is True
            assert workflow_result.steps_completed > 0

    def test_ipt_wt_pattern_execution(self):
        """Test IPT-WT pattern workflow execution."""

        # Create IPT-WT workflow
        ipt_wt_workflow = {
            'name': 'test_ipt_wt',
            'version': '2.0',
            'metadata': {
                'orchestration_pattern': 'ipt_wt'
            },
            'roles': {
                'ipt': {
                    'tools': ['ai_analyst'],
                    'responsibilities': ['planning', 'analysis']
                },
                'wt': {
                    'tools': ['code_fixers'],
                    'responsibilities': ['execution']
                }
            },
            'phases': [
                {
                    'id': 'planning',
                    'role': 'ipt',
                    'tasks': ['analyze_requirements']
                },
                {
                    'id': 'execution',
                    'role': 'wt',
                    'depends_on': ['planning'],
                    'tasks': ['apply_fixes']
                }
            ]
        }

        workflow_file = self.temp_dir / 'ipt_wt_workflow.yaml'
        with open(workflow_file, 'w') as f:
            json.dump(ipt_wt_workflow, f, indent=2)

        # Test IPT-WT execution
        result = self.workflow_runner.run(
            workflow_file=workflow_file,
            coordination_mode='ipt_wt',
            dry_run=True
        )

        assert result.success is True
        assert result.steps_completed > 0

    @patch('subprocess.run')
    def test_git_coordination_integration(self, mock_subprocess):
        """Test git operations coordination."""

        # Mock git command responses
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "main\n"
        mock_subprocess.return_value.stderr = ""

        workflows = [
            {'name': 'workflow_1', 'metadata': {'id': 'wf1'}},
            {'name': 'workflow_2', 'metadata': {'id': 'wf2'}}
        ]

        # Test git operations adapter integration
        from src.cli_multi_rapid.adapters.git_ops import GitOpsAdapter
        git_adapter = GitOpsAdapter()

        # Test coordination branch creation
        branch_map = git_adapter.create_coordination_branches(workflows)

        assert len(branch_map) == 2
        assert 'wf1' in branch_map
        assert 'wf2' in branch_map

        for workflow_id, branch_info in branch_map.items():
            assert 'branch_name' in branch_info
            assert 'base_branch' in branch_info
            assert 'created_at' in branch_info

    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""

        # Test with invalid workflow
        invalid_workflow = {
            'name': 'invalid_workflow',
            # Missing required fields
        }

        workflow_file = self.temp_dir / 'invalid_workflow.yaml'
        with open(workflow_file, 'w') as f:
            json.dump(invalid_workflow, f)

        # Should handle invalid workflow gracefully
        result = self.workflow_runner.run(
            workflow_file=workflow_file,
            dry_run=True
        )

        assert result.success is False
        assert 'validation' in result.error.lower() or 'schema' in result.error.lower()

        # Test merge queue error recovery
        # Add item with invalid data
        try:
            self.merge_queue.add_to_queue(
                branch='',  # Invalid empty branch
                workflow_id='test_workflow'
            )
        except Exception:
            pass  # Expected to fail

        # Queue should still be functional
        status = self.merge_queue.get_queue_status()
        assert isinstance(status, dict)

    def test_performance_metrics(self):
        """Test performance metrics collection."""

        coordination_id = "coord_test_performance"

        # Simulate multiple workflow executions
        for i in range(5):
            self.cost_tracker.track_coordinated_cost(
                coordination_id=coordination_id,
                workflow_id=f'workflow_{i}',
                operation=f'operation_{i}',
                tokens_used=100 + i * 50,
                model='claude-3'
            )

        # Get coordination summary
        summary = self.cost_tracker.get_coordination_summary(coordination_id)

        assert summary['coordination_id'] == coordination_id
        assert summary['total_operations'] == 5
        assert summary['total_cost'] > 0
        assert len(summary['workflows']) == 5

        # Test security summary
        security_summary = self.security_manager.get_security_summary(coordination_id)

        assert security_summary['coordination_id'] == coordination_id
        assert 'total_violations' in security_summary
        assert 'timestamp' in security_summary


if __name__ == '__main__':
    pytest.main([__file__, '-v'])