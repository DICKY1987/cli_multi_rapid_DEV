#!/usr/bin/env python3
"""
Base Adapter Interface

Defines the abstract interface that all CLI Orchestrator adapters must implement.
Supports both deterministic tools and AI services with consistent execution patterns.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AdapterType(Enum):
    """Types of adapters supported by the orchestrator."""

    DETERMINISTIC = "deterministic"
    AI = "ai"


@dataclass
class AdapterResult:
    """Standard result format for all adapter executions."""

    success: bool
    tokens_used: int = 0
    artifacts: List[str] = field(default_factory=list)
    output: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format expected by workflow runner."""
        return {
            "success": self.success,
            "tokens_used": self.tokens_used,
            "artifacts": self.artifacts,
            "output": self.output or "",
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseAdapter(ABC):
    """Abstract base class for all workflow step adapters."""

    def __init__(self, name: str, adapter_type: AdapterType, description: str):
        self.name = name
        self.adapter_type = adapter_type
        self.description = description
        self.logger = logging.getLogger(f"adapter.{name}")

    @abstractmethod
    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """
        Execute a workflow step.

        Args:
            step: The workflow step definition containing actor, with, emits, etc.
            context: Additional context from workflow execution
            files: File pattern for operations (e.g., "src/**/*.py")

        Returns:
            AdapterResult with execution details
        """
        pass

    @abstractmethod
    def validate_step(self, step: Dict[str, Any]) -> bool:
        """
        Validate that this adapter can execute the given step.

        Args:
            step: The workflow step definition

        Returns:
            True if step is valid for this adapter
        """
        pass

    @abstractmethod
    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """
        Estimate the token cost of executing this step.

        Args:
            step: The workflow step definition

        Returns:
            Estimated token usage (0 for deterministic tools)
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Get adapter metadata for router registration."""
        return {
            "type": self.adapter_type.value,
            "description": self.description,
            "cost": self.estimate_cost({}),  # Base cost estimate
            "available": self.is_available(),
        }

    def is_available(self) -> bool:
        """Check if this adapter is available and can be used."""
        return True

    def supports_files(self) -> bool:
        """Whether this adapter supports file pattern operations."""
        return True

    def supports_with_params(self) -> bool:
        """Whether this adapter supports 'with' parameters."""
        return True

    def _extract_with_params(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Extract 'with' parameters from step definition."""
        return step.get("with", {})

    def _extract_emit_paths(self, step: Dict[str, Any]) -> List[str]:
        """Extract 'emits' artifact paths from step definition."""
        emits = step.get("emits", [])
        if isinstance(emits, str):
            return [emits]
        return emits if isinstance(emits, list) else []

    def _log_execution_start(self, step: Dict[str, Any]) -> None:
        """Log the start of step execution."""
        step_name = step.get("name", "Unnamed step")
        self.logger.info(f"Starting execution: {step_name}")

    def _log_execution_complete(self, result: AdapterResult) -> None:
        """Log the completion of step execution."""
        status = "SUCCESS" if result.success else "FAILED"
        self.logger.info(
            f"Execution {status}: tokens={result.tokens_used}, artifacts={len(result.artifacts)}"
        )
        if result.error:
            self.logger.error(f"Error: {result.error}")
