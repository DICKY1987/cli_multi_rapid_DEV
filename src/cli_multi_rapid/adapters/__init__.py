#!/usr/bin/env python3
"""
CLI Orchestrator Adapter Framework

Base classes and interfaces for implementing tool and AI adapters that execute
workflow steps in a deterministic and auditable manner.
"""

from .adapter_registry import AdapterRegistry
from .ai_analyst import AIAnalystAdapter
from .base_adapter import AdapterResult, AdapterType, BaseAdapter
from .code_fixers import CodeFixersAdapter
from .cost_estimator import CostEstimatorAdapter
from .git_ops import GitOpsAdapter
from .pytest_runner import PytestRunnerAdapter
from .vscode_diagnostics import VSCodeDiagnosticsAdapter

__all__ = [
    "BaseAdapter",
    "AdapterResult",
    "AdapterType",
    "AdapterRegistry",
    "AIAnalystAdapter",
    "CodeFixersAdapter",
    "CostEstimatorAdapter",
    "GitOpsAdapter",
    "PytestRunnerAdapter",
    "VSCodeDiagnosticsAdapter",
]
