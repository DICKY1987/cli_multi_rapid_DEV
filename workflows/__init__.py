"""
Workflow Orchestration System
Enterprise-grade workflow automation for CLI Multi-Rapid framework
"""

from .orchestrator import (
    ActionResult,
    ActionType,
    PhaseResult,
    PhaseStatus,
    WorkflowOrchestrator,
)

__all__ = [
    "WorkflowOrchestrator",
    "PhaseStatus",
    "ActionType",
    "ActionResult",
    "PhaseResult",
]

__version__ = "1.0.0"
